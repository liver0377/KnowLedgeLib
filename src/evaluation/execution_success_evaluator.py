from typing import Any

from evaluation.base import BaseEvaluator


class ExecutionSuccessEvaluator(BaseEvaluator):
    """SQL 执行成功评估器"""

    @property
    def name(self) -> str:
        return "execution_success"

    def evaluate(self, output: str, context: dict[str, Any]) -> tuple[float, str]:
        """
        评估 SQL 执行是否成功

        通过 context 中的 sql_exec_error 判断：
        - sql_exec_error 为空 → 执行成功 (score=1.0)
        - sql_exec_error 有值 → 执行失败 (score=0.0)

        Args:
            output: SQL 或结果文本（此评估器不需要）
            context: 评估上下文，应包含 sql_exec_error 字段
        """
        sql_error = context.get("sql_exec_error", "")

        if sql_error:
            return 0.0, f"SQL execution failed: {sql_error}"
        else:
            return 1.0, "SQL executed successfully"
