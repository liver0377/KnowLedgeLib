"""评估器基类定义"""

from abc import ABC, abstractmethod
from typing import Any


class BaseEvaluator(ABC):
    """评估器抽象基类"""

    @property
    @abstractmethod
    def name(self) -> str:
        """评估器名称，如 'rag_citation_present'"""
        pass

    @abstractmethod
    def evaluate(self, output: str, context: dict[str, Any]) -> tuple[float, str]:
        """
        执行评估

        Args:
            output: 模型输出
            context: 评估上下文 (trace_id, input, retrieved_docs, etc.)

        Returns:
            (score, comment): 分数和说明
        """
        pass

    def is_enabled(self, settings: Any) -> bool:
        """
        检查评估器是否启用
        默认返回 True，子类可覆盖实现更复杂的条件
        """
        return True
