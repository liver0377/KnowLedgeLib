import logging
import re
from typing import Any, Literal

from langfuse import Langfuse

from core import settings
from evaluation.base import BaseEvaluator

logger = logging.getLogger(__name__)

CITATION_PATTERN = r"\[[^\]]+\]\(/kb/files/[0-9a-f\-]+/download\)"


class CitationEvaluator(BaseEvaluator):
    """引用存在性评估器"""

    @property
    def name(self) -> str:
        return "rag_citation_present"

    def evaluate(self, output: str, context: dict[str, Any]) -> tuple[float, str]:
        """执行评估"""
        if not output or not isinstance(output, str):
            return 0.0, "Empty or invalid output"

        citations = re.findall(CITATION_PATTERN, output)
        has_citation = len(citations) > 0
        score = 1.0 if has_citation else 0.0
        comment = f"Found {len(citations)} citation(s)" if citations else "No citations found"
        return score, comment

    def _check_citation(self, output: str) -> bool:
        """检查是否包含引用（内部方法）"""
        return bool(re.search(CITATION_PATTERN, output))


def evaluate_citation_present(output: str) -> bool:
    """
    检测回答中是否包含至少一个引用链接。

    Args:
        output: AI 模型输出的文本内容

    Returns:
        bool: 如果包含至少一个引用链接返回 True，否则返回 False

    Example:
        >>> evaluate_citation_present("参见 [文档](/kb/files/123/download)")
        True
        >>> evaluate_citation_present("没有引用")
        False
    """
    if not output or not isinstance(output, str):
        return False
    return bool(re.search(CITATION_PATTERN, output))


def record_citation_score(
    trace_id: str,
    output: str,
    enabled: bool | None = None,
) -> None:
    """
    记录引用存在性评分到 Langfuse。

    Args:
        trace_id: Langfuse trace ID
        output: AI 模型输出的文本内容
        enabled: 是否启用评估，None 时使用 settings.LANGFUSE_AUTO_EVAL

    Returns:
        None

    Note:
        - 评估失败不会抛出异常，仅记录日志
        - 如果 LANGFUSE_TRACING 为 False，则不会记录
    """
    if enabled is None:
        enabled = settings.LANGFUSE_AUTO_EVAL

    if not enabled or not settings.LANGFUSE_TRACING:
        return

    try:
        has_citation = evaluate_citation_present(output)
        citations = re.findall(CITATION_PATTERN, output)

        langfuse = Langfuse()
        langfuse.create_score(
            name="rag_citation_present",
            value=1.0 if has_citation else 0.0,
            trace_id=trace_id,
            comment=f"Found {len(citations)} citation(s)" if citations else "No citations found",
            data_type="BOOLEAN",
        )

        logger.info(
            f"Recorded citation score for trace {trace_id}: "
            f"{1.0 if has_citation else 0.0} ({len(citations)} citations)"
        )
    except Exception as e:
        logger.warning(f"Failed to record citation score for trace {trace_id}: {e}")


def evaluate_citation_present_with_details(
    output: str,
) -> dict[Literal["has_citation", "count", "citations"], object]:
    """
    评估引用存在性并返回详细信息。

    Args:
        output: AI 模型输出的文本内容

    Returns:
        dict: 包含以下键的字典
            - has_citation: bool, 是否包含引用
            - count: int, 引用数量
            - citations: list[str], 所有找到的引用链接

    Example:
        >>> result = evaluate_citation_present_with_details("参见 [文档](/kb/files/123/download)")
        >>> result["has_citation"]
        True
        >>> result["count"]
        1
    """
    if not output or not isinstance(output, str):
        return {"has_citation": False, "count": 0, "citations": []}

    citations = re.findall(CITATION_PATTERN, output)
    return {
        "has_citation": len(citations) > 0,
        "count": len(citations),
        "citations": citations,
    }
