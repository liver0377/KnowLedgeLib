import os
from typing import Any
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from core import get_model, settings
from agents.knowledge_base_agent.state import AgentState
from agents.knowledge_base_agent.retrievers import make_retriever
from agents.knowledge_base_agent.prompts import TEXT2SQL_SYSTEM, build_text2sql_user_prompt


def _summarize_docs(docs) -> list[dict[str, Any]]:
    """返回普通list[dict]"""
    out = []
    for i, d in enumerate(docs, 1):
        out.append(
            {
                "id": d.metadata.get("id", f"doc-{i}"),
                "doc_type": d.metadata.get("doc_type"),
                "database": d.metadata.get("database"),
                "table_name": d.metadata.get("table_name"),
                "source": d.metadata.get("source", "Unknown"),
                "content": d.page_content,
                "sql": d.metadata.get("sql"),
            }
        )
    return out


async def resolve_target_db(state: AgentState, config: RunnableConfig) -> AgentState:
    """
    解析目标数据库，并验证用户权限

    从 configurable 传入（例如前端选择了数据库），如果没有则使用默认数据库
    检查用户是否有权限访问该数据库
    """
    from service.text2sql_permissions import should_use_analytics_views

    # 获取用户上下文
    user_context = state.get("user_context", {})

    # 优先从 configurable 传入（例如前端选择了数据库）
    db = config["configurable"].get("target_db") if "configurable" in config else None
    if not db:
        db = os.getenv("DEFAULT_DB", "")

    # 检查 text2sql 权限
    can_use_text2sql = user_context.get("can_use_text2sql", False)
    if not can_use_text2sql:
        return {"target_db": db, "error": "您没有使用 Text2SQL 的权限，请联系管理员"}

    # 检查数据库访问权限
    allowed_databases = user_context.get("text2sql_allowed_databases", [])
    if db not in allowed_databases:
        return {"target_db": db, "error": f"您无权访问数据库: {db}"}

    # 判断是否使用 analytics 视图
    use_analytics_views = should_use_analytics_views(
        user_context.get("roles", []), user_context.get("permissions", set())
    )

    return {"target_db": db, "use_analytics_views": use_analytics_views}


async def retrieve_sql_schema(state: AgentState, config: RunnableConfig) -> AgentState:
    """
    获取table的schema以及字段信息，并根据用户权限过滤
    """
    from service.text2sql_permissions import Text2SQLPermissionDAO

    collection = os.getenv("MILVUS_COLLECTION_SQL", "knowledge_base_sql")
    db = state.get("target_db", "")

    # 获取用户上下文
    user_context = state.get("user_context", {})
    roles = user_context.get("roles", [])

    # 检查是否有错误
    if state.get("error"):
        return {"error": state["error"]}

    expr = 'metadata["doc_type"] in ["ddl","description"]'
    if db:
        expr += f' and metadata["database"] == "{db}"'

    # 获取允许访问的表列表（analyst 只能访问非敏感数据）
    allowed_tables = Text2SQLPermissionDAO.get_allowed_tables_for_user(db, roles)

    # 如果有表权限限制，添加过滤条件
    if allowed_tables and "admin" not in roles:
        table_filter = " or ".join([f'metadata["table_name"] == "{t}"' for t in allowed_tables])
        expr += f" and ({table_filter})"

    retriever = make_retriever(collection_name=collection, k=6, expr=expr)

    human = next((m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)), None)
    query = human.content if human else ""

    docs = await retriever.ainvoke(query)
    return {"sql_schema_docs": _summarize_docs(docs)}


async def retrieve_sql_examples(state: AgentState, config: RunnableConfig) -> AgentState:
    """
    获取自然语言 -> sql的示例
    """
    collection = os.getenv("MILVUS_COLLECTION_SQL", "knowledge_base_sql")
    db = state.get("target_db", "")

    expr = 'metadata["doc_type"] == "qsql"'
    if db:
        expr += f' and metadata["database"] == "{db}"'

    retriever = make_retriever(collection_name=collection, k=3, expr=expr)

    human = next((m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)), None)
    query = human.content if human else ""

    docs = await retriever.ainvoke(query)
    return {"sql_example_docs": _summarize_docs(docs)}


async def prepare_sql_context(state: AgentState, config: RunnableConfig) -> AgentState:
    schema = state.get("sql_schema_docs", [])
    ex = state.get("sql_example_docs", [])

    parts = []
    parts.append("## SCHEMA / DDL / DESCRIPTION")
    for i, d in enumerate(schema, 1):
        parts.append(
            f"--- SCHEMA {i} (type={d.get('doc_type')}, table={d.get('table_name')}) ---\n{d.get('content', '')}"
        )

    parts.append("\n## FEW-SHOT QSQL EXAMPLES")
    for i, d in enumerate(ex, 1):
        parts.append(
            f"--- EXAMPLE {i} ---\n"
            f"Question: {d.get('content', '')}\n"
            f"SQL: {d.get('sql', '(missing)')}"
        )

    return {"sql_context": "\n\n".join(parts)}


async def generate_sql(state: AgentState, config: RunnableConfig) -> AgentState:
    m = get_model(config["configurable"].get("model", settings.DEFAULT_MODEL))

    human = next((m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)), None)
    question = human.content if human else ""

    user_prompt = build_text2sql_user_prompt(
        question=question,
        target_db=state.get("target_db", ""),
        sql_context=state.get("sql_context", ""),
    )

    resp = await m.ainvoke(
        [
            SystemMessage(content=TEXT2SQL_SYSTEM),
            HumanMessage(content=user_prompt),
        ]
    )

    # 你可以要求模型"只输出 SQL"，则这里直接当 SQL
    return {
        "messages": [],
        "generated_sql": resp.content,
        "sql_trace_id": str(resp.id),
    }
