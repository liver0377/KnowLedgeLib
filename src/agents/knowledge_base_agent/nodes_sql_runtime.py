from __future__ import annotations
import asyncio
import os
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from dataclasses import dataclass
from langchain_core.runnables import RunnableConfig
from core import get_model, settings
from agents.knowledge_base_agent.state import AgentState, SqlFlowState
from agents.knowledge_base_agent.sql_utils import extract_sql, ensure_limit, to_markdown_table
from agents.knowledge_base_agent.prompts import REPAIR_SYSTEM, build_repair_sql_prompt
from agents.knowledge_base_agent.sql_validator import validate_sql_
from agents.knowledge_base_agent.sql_executor import execute_select
from evaluation import EvaluationManager, ExecutionSuccessEvaluator

import logging

logger = logging.getLogger(__file__)

evaluation_manager = EvaluationManager()
evaluation_manager.register(ExecutionSuccessEvaluator())


async def repair_sql(state: AgentState, config: RunnableConfig) -> AgentState:
    """使用 llm 修复语义错误的 SQL 语句"""
    m = get_model(config["configurable"].get("model", settings.DEFAULT_MODEL))
    dialect = state.get("sql_dialect", "")

    error = state.get("sql_validation_error", "")
    bad_sql = state.get("generated_sql", "")
    ctx = state.get("sql_context", "")

    prompt = build_repair_sql_prompt(ctx=ctx, bad_sql=bad_sql, dialect=dialect, error=error)

    resp = await m.ainvoke(
        [
            SystemMessage(content=REPAIR_SYSTEM),
            HumanMessage(content=prompt),
        ]
    )

    fixed = extract_sql(resp.content)
    return {
        "generated_sql": fixed,
        "sql_attempt": state.get("sql_attempt", 0) + 1,
        "sql_validation_error": "",
        "sql_exec_error": "",
        "sql_error_stage": "",
        "sql_error_type": "",
        "sql_flow_state": SqlFlowState.INIT,
    }


async def validate_sql(state: AgentState, config: RunnableConfig) -> AgentState:
    """
    校验 sql 语句是否满足权限要求，并进行规范化
    包括: SELECT 限制、多语句检查、LIMIT 验证
    """
    from service.text2sql_permissions import check_sql_type_restrictions, validate_sql_limit

    dialect = os.getenv("SQL_DIALECT", "mysql")
    sql = state.get("generated_sql", "")

    # 从 configurable 获取用户角色
    configurable = config.get("configurable", {})
    roles = configurable.get("roles", [])

    # 基础 SQL 类型验证
    type_valid, type_error = check_sql_type_restrictions(sql)
    if not type_valid:
        return {
            "validated_sql": "",
            "sql_validation_error": type_error,
            "sql_error_stage": "validate",
            "sql_error_type": "not_select",
            "sql_flow_state": SqlFlowState.VALID_NOT_SELECT,
        }

    # 验证 LIMIT 子句（analyst 角色必须有限制）
    if "admin" not in roles:
        from core import settings

        default_limit = getattr(settings, "ANALYST_DEFAULT_LIMIT", 2000)
        max_limit = getattr(settings, "ANALYST_MAX_LIMIT", 10000)

        limit_valid, limit_msg, limit_value = validate_sql_limit(sql, default_limit, max_limit)
        if not limit_valid:
            return {
                "validated_sql": "",
                "sql_validation_error": limit_msg,
                "sql_error_stage": "validate",
                "sql_error_type": "parse_error",
                "sql_flow_state": SqlFlowState.VALID_ERROR,
            }

    # 使用 sqlglot 进行规范化验证
    vr = validate_sql_(sql, dialect=dialect)

    if not vr.ok:
        err = vr.error or "validate_failed"
        error_type = "not_select" if "Only SELECT" in err else "parse_error"

        return {
            "validated_sql": "",
            "sql_validation_error": err,
            "sql_error_stage": "validate",
            "sql_error_type": error_type,
            "sql_flow_state": SqlFlowState.VALID_ERROR,
        }

    return {
        "validated_sql": vr.normalized_sql,
        "sql_validation_error": "",
        "sql_error_stage": "",
        "sql_error_type": "",
        "sql_flow_state": SqlFlowState.VALID_OK,
    }


async def execute_sql(state: AgentState, config: RunnableConfig) -> AgentState:
    """
    执行 sql 语句，并对结果进行脱敏处理
    """
    from service.text2sql_permissions import mask_query_result, extract_table_name_from_sql

    sql = state.get("validated_sql") or state.get("generated_sql") or ""

    # 从 configurable 获取用户角色
    configurable = config.get("configurable", {})
    roles = configurable.get("roles", [])
    db = state.get("target_db", "")

    # 强制 LIMIT
    if "admin" not in roles:
        from core import settings

        limit = int(getattr(settings, "ANALYST_DEFAULT_LIMIT", 2000))
    else:
        limit = int(os.getenv("SQL_MAX_ROWS", "200"))

    sql = ensure_limit(sql, limit=limit)

    loop = asyncio.get_running_loop()
    # 用线程池做异步 sql 执行
    timeout_s = int(os.getenv("TIMEOUT_S", "10"))
    result = await loop.run_in_executor(
        None,  # 默认线程池
        lambda: execute_select(sql, timeout_s=timeout_s, max_rows=limit),
    )

    if not result.ok:
        return {
            "sql_exec_error": result.error,
            "sql_exec_rows": [],
            "sql_exec_columns": [],
            "sql_exec_rowcount": 0,
            "sql_flow_state": SqlFlowState.EXEC_ERROR,
        }

    # 对查询结果进行脱敏处理
    table_name = extract_table_name_from_sql(sql)
    masked_rows = result.rows

    if table_name and db:
        masked_rows = mask_query_result(result.rows, db, table_name, roles)

    return {
        "sql_exec_error": "",
        "sql_exec_rows": masked_rows,
        "sql_exec_columns": result.columns,
        "sql_exec_rowcount": result.rowcount,
        "validated_sql": sql,
        "sql_flow_state": SqlFlowState.EXEC_OK,
    }


async def format_sql_result(state: AgentState, config: RunnableConfig) -> AgentState:
    trace_id = state.get("sql_trace_id")

    if state.get("sql_exec_error"):
        # 这里也可以选择交给 repair_sql 再试一次（见下方 graph）
        msg = f"执行SQL失败: {state['sql_exec_error']}\n\n```sql\n{state.get('validated_sql') or state.get('generated_sql')}\n```"

        if trace_id:
            evaluation_manager.evaluate_all(
                output="",
                context={
                    "trace_id": trace_id,
                    "sql_exec_error": state.get("sql_exec_error"),
                },
            )

        return {"messages": [AIMessage(content=msg)]}

    cols = state.get("sql_exec_columns", [])
    rows = state.get("sql_exec_rows", [])
    sql = state.get("validated_sql") or state.get("generated_sql") or ""

    table = to_markdown_table(cols, rows)
    msg = f"```sql\n{sql}\n```\n\n查询结果(最多返回 {len(rows)} 行）：\n\n{table}"

    if trace_id:
        evaluation_manager.evaluate_all(
            output="",
            context={
                "trace_id": trace_id,
                "sql_exec_error": "",
            },
        )

    logger.warning(f"format message: {msg}")
    return {"messages": [AIMessage(content=msg)]}


MAX_ATTEMPTS = 5


async def sql_transition(state: AgentState, config: RunnableConfig) -> AgentState:
    """统一决策节点：根据 sql_flow_state 和 sql_attempt 决定下一步"""
    flow_state = state.get("sql_flow_state")
    attempt = int(state.get("sql_attempt", 0) or 0)

    termination_reason = None

    if flow_state == SqlFlowState.VALID_OK:
        next_node = "execute_sql"

    elif flow_state == SqlFlowState.VALID_NOT_SELECT:
        termination_reason = "not_select"
        next_node = "format_sql_result"

    elif flow_state == SqlFlowState.VALID_ERROR:
        if attempt < MAX_ATTEMPTS:
            next_node = "repair_sql"
        else:
            termination_reason = "validate_max"
            next_node = "format_sql_result"

    elif flow_state == SqlFlowState.EXEC_OK:
        termination_reason = "exec_ok"
        next_node = "format_sql_result"

    elif flow_state == SqlFlowState.EXEC_ERROR:
        if attempt < MAX_ATTEMPTS:
            next_node = "repair_sql"
        else:
            termination_reason = "exec_max"
            next_node = "format_sql_result"

    else:
        termination_reason = "unknown"
        next_node = "format_sql_result"

    result = {
        "next_node": next_node,
    }

    if termination_reason:
        result["termination_reason"] = termination_reason

    return result
