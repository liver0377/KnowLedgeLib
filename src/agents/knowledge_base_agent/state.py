from enum import Enum
from typing import Any, Literal
from langgraph.graph import MessagesState
from langgraph.managed import RemainingSteps


class SqlFlowState(str, Enum):
    INIT = "init"
    VALID_OK = "valid_ok"
    VALID_NOT_SELECT = "valid_not_select"
    VALID_ERROR = "valid_error"
    EXEC_OK = "exec_ok"
    EXEC_ERROR = "exec_error"


class AgentState(MessagesState, total=False):
    route: Literal["text2sql", "doc"]
    remaining_steps: RemainingSteps

    # doc RAG
    retrieved_documents: list[dict[str, Any]]
    kb_documents: str

    # text2sql
    sql_dialect: str  # sql方言
    sql_schema_docs: list[dict[str, Any]]
    sql_example_docs: list[dict[str, Any]]
    sql_context: str  # schema + examples 拼成的上下文
    generated_sql: str  # 会被repair_sql 反复覆盖
    validated_sql: str  # 经过校验规范化之后的 SQL, 会被valida_sql复覆盖
    sql_validation_error: str  # SQL校验错误
    target_db: str  # 目标数据库（可从 config 或用户问题解析）
    sql_trace_id: str  # 保存 generate_sql 的 response.id，用于 langfuse trace

    sql_exec_rows: list[dict]  # 执行结果（每行 dict）
    sql_exec_columns: list[str]
    sql_exec_rowcount: int
    sql_exec_error: str

    sql_attempt: int  # 重试次数
    sql_flow_state: SqlFlowState  # SQL流程状态
    next_node: str  # 图路由用的临时字段
    termination_reason: str  # exec_ok/validate_max/exec_max/not_select/parse_error/exec_error
    sql_error_stage: str  # validate/execute
    sql_error_type: str  # not_select/parse_error/runtime_error
