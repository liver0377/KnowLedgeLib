"""评估管理器，统一管理所有评估器"""

import logging
from typing import Any

from langfuse import Langfuse

from core import settings

from .base import BaseEvaluator

logger = logging.getLogger(__name__)


class EvaluationManager:
    """评估管理器，负责注册和执行评估器"""

    def __init__(self):
        self._evaluators: list[BaseEvaluator] = []

    def register(self, evaluator: BaseEvaluator) -> None:
        """注册一个评估器"""
        self._evaluators.append(evaluator)
        logger.debug(f"Registered evaluator: {evaluator.name}")

    def evaluate_all(self, output: str, context: dict[str, Any]) -> None:
        """
        执行所有启用的评估

        Args:
            output: 模型输出
            context: 评估上下文
        """
        if not settings.LANGFUSE_TRACING or not settings.LANGFUSE_AUTO_EVAL:
            return

        for evaluator in self._evaluators:
            try:
                if evaluator.is_enabled(settings):
                    self._record_score(evaluator, output, context)
            except Exception as e:
                logger.warning(f"Evaluator '{evaluator.name}' failed: {e}")

    def _record_score(self, evaluator: BaseEvaluator, output: str, context: dict[str, Any]) -> None:
        """记录单个评估器的分数到 Langfuse"""
        try:
            score, comment = evaluator.evaluate(output, context)

            langfuse = Langfuse()
            langfuse.create_score(
                name=evaluator.name,
                value=score,
                trace_id=context.get("trace_id"),
                comment=comment,
                data_type="BOOLEAN" if score in (0.0, 1.0) else "NUMERIC",
            )

            logger.info(f"Recorded {evaluator.name}={score} for trace {context.get('trace_id')}")
        except Exception as e:
            logger.warning(f"Failed to record score for {evaluator.name}: {e}")
