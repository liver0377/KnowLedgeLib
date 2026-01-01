from __future__ import annotations
import asyncio
import os
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from dataclasses import dataclass
from langchain_core.runnables import RunnableConfig
from core import get_model, settings
from agents.knowledge_base_agent.state import AgentState
from agents.knowledge_base_agent.sql_utils import extract_sql, ensure_limit, to_markdown_table
from agents.knowledge_base_agent.prompts import REPAIR_SYSTEM, build_repair_sql_prompt
from agents.knowledge_base_agent.sql_validator import validate_sql_
from agents.knowledge_base_agent.sql_executor import execute_select


async def repair_sql(state: AgentState, config: RunnableConfig) -> AgentState:
    """ 使用 llm 修复语义错误的 SQL 语句"""
    m = get_model(config["configurable"].get("model", settings.DEFAULT_MODEL))
    dialect = state.get("sql_dialect", "")

    error = state.get("sql_validation_error", "")
    bad_sql = state.get("generated_sql", "")
    ctx = state.get("sql_context", "")

    prompt = build_repair_sql_prompt(ctx=ctx, bad_sql=bad_sql, dialect=dialect, error=error)

    resp = await m.ainvoke([
        SystemMessage(content=REPAIR_SYSTEM),
        HumanMessage(content=prompt),
    ])

    fixed = extract_sql(resp.content)
    return {
        "generated_sql": fixed,   # 用 generated_sql 覆盖成新版本
        "sql_attempt": state.get("sql_attempt", 0) + 1,
        "messages": [],           # 修复中间不直接回复用户
    }


async def validate_sql(state: AgentState, config: RunnableConfig) -> AgentState:
    """校验 sql 语句是否满足权限要求，并进行规范化"""
    dialect = os.getenv("SQL_DIALECT", "mysql")
    sql = state.get("generated_sql", "")
    vr = validate_sql_(sql, dialect=dialect)

    if not vr.ok:
        err = vr.error or "validate_failed"
        error_type = "not_select" if "Only SELECT" in err else "parse_error"

        return {
            "sql_attempt": state.get("sql_attempt", 0) + 1,
            "validated_sql": "",
            "sql_validation_error": err,
            "sql_error_stage": "validate",
            "sql_error_type": error_type,
        }

    return {
        "validated_sql": vr.normalized_sql,
        "sql_validation_error": "",
        "sql_error_stage": "",
        "sql_error_type": "",
    }


async def execute_sql(state: AgentState, config: RunnableConfig) -> AgentState:
    """执行 sql 语句"""
    sql = state.get("validated_sql") or state.get("generated_sql") or ""
    # 强制 LIMIT
    limit = int(os.getenv("SQL_MAX_ROWS", "200"))
    sql = ensure_limit(sql, limit=limit)

    loop = asyncio.get_running_loop()
    # 用线程池做异步 sql 执行
    timeout_s = int(os.getenv("TIMEOUT_S", "10"))
    result = await loop.run_in_executor(
        None,  # 默认线程池
        lambda: execute_select(sql, timeout_s=timeout_s, max_rows=limit)
    )

    if not result.ok:
        return {"sql_exec_error": result.error, "sql_exec_rows": [], "sql_exec_columns": [], "sql_exec_rowcount": 0}

    return {
        "sql_exec_error": "",
        "sql_exec_rows": result.rows,
        "sql_exec_columns": result.columns,
        "sql_exec_rowcount": result.rowcount,
        "validated_sql": sql,  # 把加了limit的版本存下来
    }

async def format_sql_result(state: AgentState, config: RunnableConfig) -> AgentState:
    if state.get("sql_exec_error"):
        # 这里也可以选择交给 repair_sql 再试一次（见下方 graph）
        msg = f"执行SQL失败: {state['sql_exec_error']}\n\n```sql\n{state.get('validated_sql') or state.get('generated_sql')}\n```"
        return {"messages": [AIMessage(content=msg)]}
    
    

    cols = state.get("sql_exec_columns", [])
    rows = state.get("sql_exec_rows", [])
    sql = state.get("validated_sql") or state.get("generated_sql") or ""

    table = to_markdown_table(cols, rows)
    msg = f"```sql\n{sql}\n```\n\n查询结果(最多返回 {len(rows)} 行）：\n\n{table}"
    return {"messages": [AIMessage(content=msg)]}

MAX_ATTEMPTS = 5 

def should_repair_after_validate(state: AgentState):
    if not state.get("sql_validation_error"):
        return "ok"

    if state.get("sql_error_type") == "not_select":
        return "not_select"

    attempt = int(state.get("sql_attempt", 0) or 0)
    if attempt < MAX_ATTEMPTS:
        return "repair"

    return "maxed"

def should_repair_after_exec(state: AgentState) -> str:
    if not state.get("sql_exec_error"):
        return "ok"

    attempt = int(state.get("sql_attempt", 0) or 0)
    if attempt < MAX_ATTEMPTS:
        return "repair"

    return "maxed"

async def mark_not_select(state: AgentState, config: RunnableConfig) -> AgentState:
    return {"termination_reason": "not_select", "messages": []}

async def mark_validate_max(state: AgentState, config: RunnableConfig) -> AgentState:
    return {"termination_reason": "validate_max", "messages": []}

async def mark_exec_max(state: AgentState, config: RunnableConfig) -> AgentState:
    return {"termination_reason": "exec_max", "messages": []}

            