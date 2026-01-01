import os
from typing import Any, Optional

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_milvus import Milvus as MilvusVectorStore  

def build_connection_args() -> dict[str, Any]:
    uri = os.environ["MILVUS_URI"]
    args: dict[str, Any] = {"uri": uri}
    if token := os.environ.get("MILVUS_TOKEN"):
        args["token"] = token
    if db_name := os.environ.get("MILVUS_DB_NAME"):
        args["db_name"] = db_name
    if os.getenv("MILVUS_TLS", "false").lower() == "true":
        args["secure"] = True
    return args

def get_embeddings(
    embedding_model_name: str = "BAAI/bge-m3",
    device: Optional[str] = None,
    normalize_embeddings: bool = True,
):
    resolved_device = device or os.getenv("EMBEDDING_DEVICE", "cpu")
    model_kwargs = {"device": resolved_device} if resolved_device else {}
    return HuggingFaceEmbeddings(
        model_name=embedding_model_name,
        model_kwargs=model_kwargs,
        encode_kwargs={"normalize_embeddings": normalize_embeddings},
    )

def make_retriever(
    collection_name: str,
    k: int = 5,
    expr: str | None = None,
):
    embeddings = get_embeddings()
    vs = MilvusVectorStore(
        embedding_function=embeddings,
        collection_name=collection_name,
        connection_args=build_connection_args(),
        primary_field="id",
        vector_field="vector",
        text_field="text",
        metadata_field="metadata",
        auto_id=False,
        search_params={"metric_type": "COSINE", "params": {"nprobe": int(os.getenv("MILVUS_NPROBE", "32"))}},
    )

    search_kwargs: dict[str, Any] = {"k": k}
    if expr:
        search_kwargs["expr"] = expr

    return vs.as_retriever(search_kwargs=search_kwargs)
