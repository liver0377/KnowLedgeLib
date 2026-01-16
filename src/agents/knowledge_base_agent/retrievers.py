import os
from typing import Any

from core.embeddings import get_cached_embeddings
from langchain_milvus import Milvus as MilvusVectorStore


def build_connection_args() -> dict[str, Any]:
    """构建 Milvus 连接参数"""
    uri = os.environ["MILVUS_URI"]
    args: dict[str, Any] = {"uri": uri}
    if token := os.environ.get("MILVUS_TOKEN"):
        args["token"] = token
    if db_name := os.environ.get("MILVUS_DB_NAME"):
        args["db_name"] = db_name
    if os.getenv("MILVUS_TLS", "false").lower() == "true":
        args["secure"] = True
    return args


def make_retriever(
    collection_name: str,
    k: int = 5,
    expr: str | None = None,
):
    """创建 Milvus 检索器

    使用统一的缓存嵌入模型实例，避免重复加载。

    Args:
        collection_name: Milvus 集合名称
        k: 返回的文档数量
        expr: 过滤表达式

    Returns:
        Milvus 向量检索器
    """
    embeddings = get_cached_embeddings()
    vs = MilvusVectorStore(
        embedding_function=embeddings,
        collection_name=collection_name,
        connection_args=build_connection_args(),
        primary_field="id",
        vector_field="vector",
        text_field="text",
        metadata_field="metadata",
        auto_id=False,
        search_params={
            "metric_type": "COSINE",
            "params": {"nprobe": int(os.getenv("MILVUS_NPROBE", "32"))},
        },
    )

    search_kwargs: dict[str, Any] = {"k": k}
    if expr:
        search_kwargs["expr"] = expr

    return vs.as_retriever(search_kwargs=search_kwargs)
