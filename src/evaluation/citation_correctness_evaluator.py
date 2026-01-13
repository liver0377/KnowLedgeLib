"""引用正确性评估器 (LLM-as-a-Judge)"""

import logging
import re
from typing import Any

from core import get_model
from evaluation.base import BaseEvaluator

logger = logging.getLogger(__name__)

CITATION_PATTERN = r"\[[^\]]+\]\(/kb/files/[0-9a-f\-]+/download\)"

JUDGE_PROMPT = """你是一个专业的 RAG 回答评估器。请评估回答中引用的正确性。

评估标准：
1. 回答中的引用链接是否真实存在且格式正确
2. 引用的内容是否确实支持回答中的结论
3. 是否存在"编造引用"或引用错误的情况

**用户问题**: {input}

**AI 回答**: {output}

请给出评分（仅 0 或 1）和简短理由：
- 1: 引用正确，确实支持回答
- 0: 引用不存在、格式错误或与回答内容不符

输出格式：JSON {{"score": 0或1, "reasoning": "简短说明"}}
"""


class CitationCorrectnessEvaluator(BaseEvaluator):
    """引用正确性评估器 - 使用 LLM 判断引用是否真实有效"""

    @property
    def name(self) -> str:
        return "rag_citation_correct"

    def evaluate(self, output: str, context: dict[str, Any]) -> tuple[float, str]:
        """
        评估引用是否正确

        如果没有引用，直接返回 0
        如果有引用，调用 LLM 判断引用是否支持回答内容
        """
        if not output or not isinstance(output, str):
            return 0.0, "Empty or invalid output"

        # 检查是否有引用
        citations = re.findall(CITATION_PATTERN, output)
        if not citations:
            return 0.0, "No citations found"

        try:
            model = get_model()
            prompt = JUDGE_PROMPT.format(
                input=context.get("input", ""),
                output=output,
            )

            result = model.invoke(prompt)

            # 尝试解析 JSON 结果
            import json

            try:
                judge_result = json.loads(result.content)
                score = float(judge_result.get("score", 0))
                reasoning = judge_result.get("reasoning", "Unable to parse reasoning")
            except json.JSONDecodeError:
                # JSON 解析失败，尝试从文本中提取分数
                if "1" in result.content and "0" not in result.content:
                    score = 1.0
                    reasoning = "Positive indication detected"
                elif "0" in result.content:
                    score = 0.0
                    reasoning = "Negative indication detected"
                else:
                    score = 0.0
                    reasoning = "Unable to determine score"

            comment = f"{reasoning} (found {len(citations)} citations)"
            return score, comment

        except Exception as e:
            logger.warning(f"LLM-as-a-Judge evaluation failed: {e}")
            return 0.0, f"Evaluation error: {str(e)}"

    def is_enabled(self, settings: Any) -> bool:
        """只有配置了 LLM 才启用"""
        try:
            get_model()
            return True
        except Exception:
            return False
