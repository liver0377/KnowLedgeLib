"""反问需求评估器"""

import re
from typing import Any

from evaluation.base import BaseEvaluator

CLARIFICATION_PATTERNS = [
    r"需要.*[知道|确认|了解|明确]",
    r"是否.*[可以|能够|需要]",
    r"[请问|请问|请问看].*",
    r"[能否|可以|能不能|是否].*[提供|告诉|说明]",
    r"[不太清楚|不确定|不清楚].*",
    r"你是.*[指|说|确认]",
    r"具体.*[是什么|指什么]",
    r"[请|麻烦].*[说明|补充|解释].*",
]


class NeedsClarificationEvaluator(BaseEvaluator):
    """反问需求评估器 - 检测是否应该反问澄清"""

    @property
    def name(self) -> str:
        return "rag_needs_clarification"

    def evaluate(self, output: str, context: dict[str, Any]) -> tuple[float, str]:
        """
        评估回答是否包含反问或不确定表达

        评分规则：
        - 1.0: 包含反问或需要澄清的表达
        - 0.0: 直接回答，无需反问
        """
        if not output or not isinstance(output, str):
            return 0.0, "Empty or invalid output"

        has_clarification = self._detect_clarification(output)

        score = 1.0 if has_clarification else 0.0

        if has_clarification:
            matched_patterns = []
            for pattern in CLARIFICATION_PATTERNS:
                if re.search(pattern, output, re.IGNORECASE):
                    matched_patterns.append(pattern)
            comment = f"Detected clarification need (matched {len(matched_patterns)} patterns)"
        else:
            comment = "Direct answer, no clarification needed"

        return score, comment

    def _detect_clarification(self, output: str) -> bool:
        """检测是否需要澄清"""
        for pattern in CLARIFICATION_PATTERNS:
            if re.search(pattern, output, re.IGNORECASE):
                return True
        return False
