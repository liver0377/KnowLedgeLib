import os
from typing import Any
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.documents import Document

from core import get_model, settings
from agents.knowledge_base_agent.state import AgentState
from agents.knowledge_base_agent.retrievers import make_retriever
from agents.knowledge_base_agent.prompts import TEXT2SQL_SYSTEM, build_text2sql_user_prompt


# Constants
SCHEMA_RETRIEVE_K = 6
EXAMPLE_RETRIEVE_K = 3
DEFAULT_COLLECTION = "knowledge_base_sql"
DOCTYPE_DDL = "ddl"
DOCTYPE_DESC = "description"
DOCTYPE_QSQL = "qsql"
DEFAULT_SOURCE = "Unknown"
MISSING_SQL_LABEL = "(missing)"


def _extract_user_question(state: AgentState) -> str:
    """从 state 中提取最后一个 HumanMessage 的内容"""
    human = next(
        (m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)),
        None,
    )
    return human.content if human else ""


def _doc_to_dict(doc: Document, idx: int) -> dict[str, Any]:
    """将单个 Document 转换为普通字典"""
    meta = doc.metadata
    return {
        "id": meta.get("id", f"doc-{idx}"),
        "doc_type": meta.get("doc_type"),
        "database": meta.get("database"),
        "table_name": meta.get("table_name"),
        "source": meta.get("source", DEFAULT_SOURCE),
        "content": doc.page_content,
        "sql": meta.get("sql"),
    }


def _summarize_docs(docs: list[Document]) -> list[dict[str, Any]]:
    """将 Document 列表转换为普通字典列表"""
    return [_doc_to_dict(doc, i) for i, doc in enumerate(docs, 1)]


def _build_metadata_filter(expr: str, db: str | None = None) -> str:
    """为表达式添加数据库过滤条件"""
    if not db:
        return expr
    return f'{expr} and metadata["database"] == "{db}"'


def _build_schema_filter(db: str, allowed_tables: list[str] | None = None) -> str:
    """构建 schema 检索的过滤表达式"""
    base_expr = f'metadata["doc_type"] in ["{DOCTYPE_DDL}", "{DOCTYPE_DESC}"]'
    expr = _build_metadata_filter(base_expr, db)

    if allowed_tables:
        table_filter = " or ".join([f'metadata["table_name"] == "{t}"' for t in allowed_tables])
        expr += f" and ({table_filter})"

    return expr


def _build_example_filter(db: str) -> str:
    """构建示例检索的过滤表达式"""
    base_expr = f'metadata["doc_type"] == "{DOCTYPE_QSQL}"'
    return _build_metadata_filter(base_expr, db)


async def _retrieve_documents(
    collection: str,
    query: str,
    k: int,
    expr: str,
) -> list[Document]:
    """检索文档的通用函数"""
    retriever = make_retriever(collection_name=collection, k=k, expr=expr)
    return await retriever.ainvoke(query)


async def resolve_target_db(state: AgentState, config: RunnableConfig) -> AgentState:
    """
    解析目标数据库，并验证用户权限

    优先从 configurable 传入（例如前端选择了数据库），如果没有则使用默认数据库
    检查用户是否有权限访问该数据库
    """
    from service.text2sql_permissions import should_use_analytics_views

    configurable = config.get("configurable", {})

    db = configurable.get("target_db") or os.getenv("TARGET_DB", "ecommerce")

    can_use_text2sql = configurable.get("can_use_text2sql", False)
    # print(f"can_use_text2sql: {can_use_text2sql}")
    if not can_use_text2sql:
        return {
            "target_db": db,
            "messages": [SystemMessage(content="您没有使用 Text2SQL 的权限，请联系管理员")],
        }

    allowed_databases = configurable.get("text2sql_allowed_databases", [])
    if db not in allowed_databases:
        return {
            "target_db": db,
            "messages": [SystemMessage(content=f"您无权访问数据库: {db}")],
        }

    use_analytics_views = should_use_analytics_views(
        configurable.get("roles", []), configurable.get("permissions", set())
    )

    return {"target_db": db, "use_analytics_views": use_analytics_views}


async def retrieve_sql_schema(state: AgentState, config: RunnableConfig) -> AgentState:
    """
    获取table的schema以及字段信息，并根据用户权限过滤
    """
    from service.text2sql_permissions import Text2SQLPermissionDAO

    db = state.get("target_db", "")
    configurable = config.get("configurable", {})
    roles = configurable.get("roles", [])

    if state.get("error"):
        return {"error": state["error"]}

    allowed_tables = Text2SQLPermissionDAO.get_allowed_tables_for_user(db, roles)
    table_filter = allowed_tables if "admin" not in roles else None

    expr = _build_schema_filter(db, table_filter)
    query = _extract_user_question(state)

    print(f"expr: {expr}")
    print(f"query: {query}")
    docs = await _retrieve_documents(
        collection=os.getenv("MILVUS_COLLECTION_SQL", DEFAULT_COLLECTION),
        query=query,
        k=SCHEMA_RETRIEVE_K,
        expr=expr,
    )

    return {"sql_schema_docs": _summarize_docs(docs)}


async def retrieve_sql_examples(state: AgentState, config: RunnableConfig) -> AgentState:
    """
    获取自然语言 -> sql的示例
    """
    db = state.get("target_db", "")
    expr = _build_example_filter(db)
    query = _extract_user_question(state)

    docs = await _retrieve_documents(
        collection=os.getenv("MILVUS_COLLECTION_SQL", DEFAULT_COLLECTION),
        query=query,
        k=EXAMPLE_RETRIEVE_K,
        expr=expr,
    )

    return {"sql_example_docs": _summarize_docs(docs)}


def _format_schema_section(schema_docs: list[dict[str, Any]]) -> str:
    """格式化 schema 部分"""
    if not schema_docs:
        return ""

    parts = ["## SCHEMA / DDL / DESCRIPTION"]
    for i, doc in enumerate(schema_docs, 1):
        doc_type = doc.get("doc_type", "")
        table_name = doc.get("table_name", "")
        content = doc.get("content", "")
        parts.append(f"--- SCHEMA {i} (type={doc_type}, table={table_name}) ---\n{content}")
    return "\n\n".join(parts)


def _format_example_section(example_docs: list[dict[str, Any]]) -> str:
    """格式化示例部分"""
    if not example_docs:
        return ""

    parts = ["## FEW-SHOT QSQL EXAMPLES"]
    for i, doc in enumerate(example_docs, 1):
        question = doc.get("content", "")
        sql = doc.get("sql", MISSING_SQL_LABEL)
        parts.append(f"--- EXAMPLE {i} ---\nQuestion: {question}\nSQL: {sql}")
    return "\n\n".join(parts)


async def prepare_sql_context(state: AgentState, config: RunnableConfig) -> AgentState:
    """
    整合 schema 和示例，构建 SQL 生成的上下文
    """
    schema_docs = state.get("sql_schema_docs", [])
    example_docs = state.get("sql_example_docs", [])

    sections = [
        _format_schema_section(schema_docs),
        _format_example_section(example_docs),
    ]

    return {"sql_context": "\n\n".join(s for s in sections if s)}


async def generate_sql(state: AgentState, config: RunnableConfig) -> AgentState:
    """
    使用 LLM 生成 SQL 语句
    """
    model = get_model(config.get("configurable", {}).get("model") or settings.DEFAULT_MODEL)

    question = _extract_user_question(state)
    user_prompt = build_text2sql_user_prompt(
        question=question,
        target_db=state.get("target_db", ""),
        sql_context=state.get("sql_context", ""),
    )

    resp = await model.ainvoke(
        [
            SystemMessage(content=TEXT2SQL_SYSTEM),
            HumanMessage(content=user_prompt),
        ]
    )

    return {
        "messages": [],
        "generated_sql": resp.content,
        "sql_trace_id": str(resp.id),
    }
