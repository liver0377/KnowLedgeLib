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
        out.append({
            "id": d.metadata.get("id", f"doc-{i}"),
            "doc_type": d.metadata.get("doc_type"),
            "database": d.metadata.get("database"),
            "table_name": d.metadata.get("table_name"),
            "source": d.metadata.get("source", "Unknown"),
            "content": d.page_content,
            "sql": d.metadata.get("sql")
        })
    return out

async def resolve_target_db(state: AgentState, config: RunnableConfig) -> AgentState:
    # 优先从 configurable 传入（例如前端选择了数据库）
    db = config["configurable"].get("target_db") if "configurable" in config else None
    if not db:
        db = os.getenv("DEFAULT_DB", "")
    return {"target_db": db}

async def retrieve_sql_schema(state: AgentState, config: RunnableConfig) -> AgentState:
    """
    获取table的shcema以及字段信息
    """
    collection = os.getenv("MILVUS_COLLECTION_SQL", "knowledge_base_sql")
    db = state.get("target_db", "")

    expr = 'metadata["doc_type"] in ["ddl","description"]'
    if db:
        expr += f' and metadata["database"] == "{db}"'

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
        parts.append(f"--- SCHEMA {i} (type={d.get('doc_type')}, table={d.get('table_name')}) ---\n{d.get('content','')}")

    parts.append("\n## FEW-SHOT QSQL EXAMPLES")
    for i, d in enumerate(ex, 1):
        parts.append(
            f"--- EXAMPLE {i} ---\n"
            f"Question: {d.get('content','')}\n"
            f"SQL: {d.get('sql','(missing)')}"
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

    resp = await m.ainvoke([
        SystemMessage(content=TEXT2SQL_SYSTEM),
        HumanMessage(content=user_prompt),
    ])

    # 你可以要求模型“只输出 SQL”，则这里直接当 SQL
    return {"messages": [], "generated_sql": resp.content}
