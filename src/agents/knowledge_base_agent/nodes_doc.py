import logging
import os

from typing import Any, List
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.runnables import RunnableConfig, RunnableSerializable, RunnableLambda, RunnableSequence
from agents.knowledge_base_agent.retrievers import make_retriever
from agents.knowledge_base_agent.state import AgentState
from agents.knowledge_base_agent.prompts import DOC_SYSTEM_PROMPT
from agents.knowledge_base_agent.authz import get_allowed_dept_keys
from core import get_model, settings

logger = logging.getLogger(__name__)


def _build_milvus_expr_for_dept_keys(allowed: list[str]) -> str | None:
    """
    return (expr, status)
    status:
      - "ALLOW_ALL"  : allowed 含 "*"
      - "ALLOW_SOME" : allowed 有具体部门
      - "DENY_ALL"   : allowed 为空
    """
    if not allowed:
        return 'metadata["dept_key"] in ["__none__"]', "DENY_ALL"  # 保证无结果
    if "*" in allowed:
        return None, "ALLOW_ALL"
    allowed_list = ", ".join([f'"{d}"' for d in allowed])
    return f'metadata["dept_key"] in [{allowed_list}]', "ALLOW_SOME"

async def retrieve_documents(state: AgentState, config: RunnableConfig) -> AgentState:
    human_messages = [msg for msg in state["messages"] if isinstance(msg, HumanMessage)]
    if not human_messages:
        return {"messages": [], "retrieved_documents": []}

    query = human_messages[-1].content

    cfg: dict[str, Any] = config.get("configurable")
    user_id: str = cfg.get("user_id", "")
    roles: list[str] = cfg.get("roles", [])
    allowed_dept_keys: list[str] = cfg.get("allowed_dept_keys") or []

    # allowed_dept_keys = get_allowed_dept_keys(user_id=user_id, roles=roles, dept_key=dept_key)
    dept_expr, authz_status = _build_milvus_expr_for_dept_keys(allowed_dept_keys)

    if dept_expr == 'metadata["dept_key"] in ["__none__"]':
        return {
            "retrieved_documents": [],
            "messages": [AIMessage(content="你当前没有访问对应企业知识库文档的权限，请联系管理员或在权限系统中申请相应部门的访问权限。")],
            "stop_chain": True
        }

    final_expr = dept_expr

    try:
        collection_name = os.getenv("MILVUS_COLLECTION_DOC")
        retriever = make_retriever(collection_name, expr=final_expr)
        retrieved_docs = await retriever.ainvoke(query)

        if not retrieved_docs:
            # 2) 允许存在性泄露：明确告诉用户“可能存在但不可见”
            # （不展示任何受限内容）
            return {
                "retrieved_documents": [],
                "messages": [AIMessage(content="未检索到你当前可访问的相关文档。由于权限限制，可能存在相关资料但你暂无权限查看；请申请相应部门的访问权限或联系管理员。")],
                "stop_chain": True,
            }

        document_summaries = []
        for i, doc in enumerate(retrieved_docs, 1):
            document_summaries.append({
                "id": doc.metadata.get("chunk_id", f"doc-{i}"),
                "source": doc.metadata.get("source", "Unknown"),
                "title": doc.metadata.get("title", f"Document {i}"),
                "content": doc.page_content,
                "relevance_score": doc.metadata.get("score", 0),
                "dept_key": doc.metadata.get("dept_key"),
            })

        return {
            "retrieved_documents": document_summaries,
            "messages": [],
            "stop_chain": False
        }

    except Exception as e:
        logger.error(f"Error retrieving documents: {str(e)}")
        return {"retrieved_documents": [], "messages": []}


async def prepare_augmented_prompt(state: AgentState, config: RunnableConfig) -> AgentState:
    """Prepare a prompt augmented with retrieved document content."""
    # Get retrieved documents
    documents = state.get("retrieved_documents", [])

    if not documents:
        return {"messages": []}

    # Format retrieved documents for the model
    formatted_docs = "\n\n".join(
        [
            f"--- Document {i + 1} ---\n"
            f"Source: {doc.get('source', 'Unknown')}\n"
            f"Title: {doc.get('title', 'Unknown')}\n\n"
            f"{doc.get('content', '')}"
            for i, doc in enumerate(documents)
        ]
    )

    # Store formatted documents in the state
    return {"kb_documents": formatted_docs, "messages": []}

def wrap_model(model: BaseChatModel) -> RunnableSerializable[AgentState, AIMessage]:
    """Wrap the model with a system prompt for the Knowledge Base agent."""

    def create_system_message(state):
        base_prompt = DOC_SYSTEM_PROMPT

        # Check if documents were retrieved
        if "kb_documents" in state:
            # Append document information to the system prompt
            document_prompt = f"\n\nI've retrieved the following documents that may be relevant to the query:\n\n{state['kb_documents']}\n\nPlease use these documents to inform your response to the user's query. Only use information from these documents and clearly indicate when you are unsure."
            return [SystemMessage(content=base_prompt + document_prompt)] + state["messages"]
        else:
            # No documents were retrieved
            no_docs_prompt = (
                "\n\nNo relevant documents were found in the knowledge base for this query."
            )
            return [SystemMessage(content=base_prompt + no_docs_prompt)] + state["messages"]

    preprocessor = RunnableLambda(
        create_system_message,
        name="StateModifier",
    )
    return RunnableSequence(preprocessor, model)

async def acall_model(state: AgentState, config: RunnableConfig) -> AgentState:
    if state.get("stop_chain"):
        # 直接把上一步的 AIMessage 返回给用户
        return {"messages": state["messages"]}

    m = get_model(config["configurable"].get("model", settings.DEFAULT_MODEL))
    model_runnable = wrap_model(m)
    response = await model_runnable.ainvoke(state, config)
    return {"messages": [response]}


