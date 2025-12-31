import logging
import os
from typing import Any, Optional

# from langchain_aws import AmazonKnowledgeBasesRetriever
# from langchain_community.embeddings import HuggingFaceBgeEmbeddings
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_milvus import Milvus
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig, RunnableLambda, RunnableSerializable
from langchain_core.runnables.base import RunnableSequence
from langgraph.graph import END, MessagesState, StateGraph
from langgraph.managed import RemainingSteps

from core import get_model, settings

logger = logging.getLogger(__name__)


# Define the state
class AgentState(MessagesState, total=False):
    """State for Knowledge Base agent."""

    remaining_steps: RemainingSteps
    retrieved_documents: list[dict[str, Any]]  # 检索到的文档
    kb_documents: str                          # 检索到的文档所对应的完整字符串


# Cerate the retriever
def get_kb_retriever(
    embedding_model_name: str = "BAAI/bge-m3",
    device: Optional[str] = None,
    normalize_embeddings: bool = True,):
    """
    创建一个Milvus retriever 实例, 使用BGE Embedding
    """
    milvus_uri = os.environ["MILVUS_URI"]
    if not milvus_uri:
        raise ValueError("MILVUS_URI environment variable must be set")
    
    collection_name = os.environ.get("MILVUS_COLLECTION")
    if not collection_name:
        raise ValueError("MILVUS COLLECTION must be set")
    
    model_kwargs = {}
    resolved_device = device or os.getenv("EMBEDDING_DEVICE", "cpu")
    if resolved_device:
        model_kwargs["device"] = resolved_device

    embeddings = HuggingFaceEmbeddings(
        model_name=embedding_model_name,
        model_kwargs=model_kwargs,
        encode_kwargs={"normalize_embeddings": normalize_embeddings},
    )

    connection_args: dict[str, Any] = {"uri": milvus_uri}
    if token := os.environ.get("MILVUS_TOKEN"):
        connection_args["token"] = token
    
    vector_store = Milvus(
        embedding_function=embeddings,
        collection_name=collection_name,
        connection_args=connection_args
    )

    return vector_store.as_retriever(search_kwargs={"k": 5})

    
def wrap_model(model: BaseChatModel) -> RunnableSerializable[AgentState, AIMessage]:
    """Wrap the model with a system prompt for the Knowledge Base agent."""

    def create_system_message(state):
        base_prompt = """你是一个乐于助人的助手，会基于检索到的文档提供准确的信息。

        你将收到一个查询，以及从知识库中检索到的相关文档。请使用这些文档来支撑你的回答。

        请遵循以下准则：
        1. 你的回答应主要基于检索到的文档
        2. 如果文档中包含答案，请清晰、简洁地给出
        3. 如果文档信息不足，请说明你没有足够的信息
        4. 绝不编造文档中不存在的事实或信息
        5. 当引用具体信息时，务必标注来源文档
        6. 如果文档之间存在矛盾，请承认并解释不同的观点

        请以清晰、自然的对话方式组织回答；在合适的情况下使用 Markdown 格式。
        """

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


async def retrieve_documents(state: AgentState, config: RunnableConfig) -> AgentState:
    """Retrieve relevant documents from the knowledge base."""
    # Get the last human message
    human_messages = [msg for msg in state["messages"] if isinstance(msg, HumanMessage)]
    if not human_messages:
        # Include messages from original state
        return {"messages": [], "retrieved_documents": []}

    # Use the last human message as the query
    query = human_messages[-1].content

    try:
        # Initialize the retriever
        retriever = get_kb_retriever()

        # Retrieve documents
        retrieved_docs = await retriever.ainvoke(query)

        # Create document summaries for the state
        document_summaries = []
        for i, doc in enumerate(retrieved_docs, 1):
            summary = {
                "id": doc.metadata.get("id", f"doc-{i}"),
                "source": doc.metadata.get("source", "Unknown"),
                "title": doc.metadata.get("title", f"Document {i}"),
                "content": doc.page_content,
                "relevance_score": doc.metadata.get("score", 0),
            }
            document_summaries.append(summary)

        logger.info(f"Retrieved {len(document_summaries)} documents for query: {query[:50]}...")

        return {"retrieved_documents": document_summaries, "messages": []}

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


async def acall_model(state: AgentState, config: RunnableConfig) -> AgentState:
    """Generate a response based on the retrieved documents."""
    m = get_model(config["configurable"].get("model", settings.DEFAULT_MODEL))
    model_runnable = wrap_model(m)

    response = await model_runnable.ainvoke(state, config)

    return {"messages": [response]}


# Define the graph
agent = StateGraph(AgentState)

# Add nodes
agent.add_node("retrieve_documents", retrieve_documents)
agent.add_node("prepare_augmented_prompt", prepare_augmented_prompt)
agent.add_node("model", acall_model)

# Set entry point
agent.set_entry_point("retrieve_documents")

# Add edges to define the flow
agent.add_edge("retrieve_documents", "prepare_augmented_prompt")
agent.add_edge("prepare_augmented_prompt", "model")
agent.add_edge("model", END)

# Compile the agent
kb_agent = agent.compile()
