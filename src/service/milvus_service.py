# service/milvus_service.py
"""
Milvus 服务模块
提供文档向量化和导入 Milvus 集合的功能
"""

import hashlib
import logging
import os
from uuid import uuid5, NAMESPACE_URL
from typing import Any

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import Docx2txtLoader, PyPDFLoader
from langchain_milvus import Milvus as MilvusVectorStore
from pymilvus import (
    Collection,
    CollectionSchema,
    DataType,
    FieldSchema,
    connections,
    utility,
)

from core.embeddings import get_cached_embeddings

logger = logging.getLogger(__name__)


def sha1_file(path: str, buf_size: int = 1024 * 1024) -> str:
    """计算文件内容的 SHA1 哈希值

    Args:
        path: 文件路径
        buf_size: 缓冲区大小，默认 1MB

    Returns:
        文件内容的 SHA1 哈希字符串
    """
    h = hashlib.sha1()
    with open(path, "rb") as f:
        while True:
            b = f.read(buf_size)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def build_milvus_connection_args(uri: str) -> dict[str, Any]:
    """构建 Milvus 连接参数

    从环境变量读取认证配置，支持 token 或 username/password 两种方式

    Args:
        uri: Milvus 服务地址

    Returns:
        包含连接参数的字典
    """
    args: dict[str, Any] = {"uri": uri}

    token = os.getenv("MILVUS_TOKEN")
    user = os.getenv("MILVUS_USERNAME")
    password = os.getenv("MILVUS_PASSWORD")
    db_name = os.getenv("MILVUS_DB_NAME")
    secure = os.getenv("MILVUS_TLS", "false").lower() == "true"

    # 互斥：优先 token；否则 user+password；两者同时存在就报错（避免不确定行为）
    if token and (user or password):
        raise ValueError("Set either MILVUS_TOKEN or MILVUS_USERNAME/MILVUS_PASSWORD, not both.")

    if token:
        args["token"] = token
    elif user or password:
        if not (user and password):
            raise ValueError("MILVUS_USERNAME and MILVUS_PASSWORD must be set together.")
        args["user"] = user
        args["password"] = password

    if db_name:
        args["db_name"] = db_name

    if secure:
        args["secure"] = True

    return args


def ensure_collection(
    collection_name: str,
    dim: int,
    drop_if_exists: bool,
    connection_args: dict,
    index_type: str = "IVF_FLAT",
    metric: str = "COSINE",
    index_params: dict[str, Any] = None,
    text_max_length: int = 8192,
):
    """确保 Milvus 集合存在，不存在则创建

    Args:
        collection_name: 集合名称
        dim: 向量维度
        drop_if_exists: 如果集合存在是否删除重建
        connection_args: 连接参数
        index_type: 索引类型，默认 IVF_FLAT
        metric: 距离度量，默认 COSINE
        index_params: 索引参数，默认 {"nlist": 1024}
        text_max_length: 文本字段最大长度，默认 8192
    """
    connections.connect("default", **connection_args)

    if utility.has_collection(collection_name):
        if drop_if_exists:
            utility.drop_collection(collection_name)
        else:
            coll = Collection(collection_name)
            try:
                coll.load()
            except Exception:
                pass
            logger.info(f"Collection `{collection_name}` already exists.")
            return

    if index_params is None:
        index_params = {"nlist": 1024}

    fields = [
        FieldSchema(
            name="id",
            dtype=DataType.VARCHAR,
            is_primary=True,
            auto_id=False,
            max_length=128,
        ),
        FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=dim),
        FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=text_max_length),
        FieldSchema(name="metadata", dtype=DataType.JSON),
    ]
    schema = CollectionSchema(fields, description="Knowledge base chunks (metadata-only)")
    coll = Collection(name=collection_name, schema=schema)

    coll.create_index(
        field_name="vector",
        index_params={
            "index_type": index_type,
            "metric_type": metric,
            "params": {**index_params},
        },
    )
    coll.load()
    logger.info(f"Collection `{collection_name}` ready. Index: {index_type}, metric: {metric}")


def get_embeddings(
    embedding_model_name: str = "BAAI/bge-m3",
    device: str | None = None,
    normalize_embeddings: bool = True,
):
    """获取 Embedding 模型（使用统一的缓存）"""
    return get_cached_embeddings(
        embedding_model_name=embedding_model_name,
        device=device,
        normalize_embeddings=normalize_embeddings,
    )

    return HuggingFaceBgeEmbeddings(
        model_name=embedding_model_name,
        model_kwargs=model_kwargs,
        encode_kwargs={
            "normalize_embeddings": normalize_embeddings,
        },
    )


def add_document_to_milvus(
    file_path: str,
    dept_key: str,
    filename: str,
    collection_name: str = None,
    chunk_size: int = 2000,
    overlap: int = 500,
) -> None:
    """将单个文档添加到 Milvus 集合

    支持的文件类型：PDF、DOCX

    处理流程：
    1. 加载文档内容
    2. 使用 RecursiveCharacterTextSplitter 分块
    3. 生成向量 embeddings
    4. 添加到 Milvus 集合

    Metadata 包含：
    - source: 文件路径
    - filename: 文件名
    - doc_id: 文件内容 SHA1（用于唯一标识）
    - page: 页码
    - chunk_index: 分块索引
    - chunk_id: 分块唯一ID
    - dept_key: 部门标识
    - file_id: 用于前端文档链接的 UUID

    Args:
        file_path: 文件路径
        dept_key: 部门标识
        filename: 文件名
        collection_name: 集合名称，默认从环境变量读取
        chunk_size: 分块大小，默认 2000
        overlap: 分块重叠大小，默认 500

    Raises:
        ValueError: 文件类型不支持
        Exception: Milvus 操作失败
    """
    # 获取集合名称
    if collection_name is None:
        collection_name = os.getenv("MILVUS_COLLECTION_DOC", "knowledge_base_doc")

    # 获取 embedding 模型名称
    embedding_model_name = os.getenv("EMBEDDING_MODEL_NAME", "BAAI/bge-m3")
    normalize_embeddings = os.getenv("NORMALIZE_EMBEDDINGS", "true").lower() == "true"

    logger.info(
        f"Processing document: {file_path}, dept_key: {dept_key}, collection: {collection_name}"
    )

    # 1. 加载文档
    filename_lower = filename.lower()
    if filename_lower.endswith(".pdf"):
        loader = PyPDFLoader(file_path)
    elif filename_lower.endswith(".docx"):
        loader = Docx2txtLoader(file_path)
    else:
        raise ValueError(f"Unsupported file type: {filename}. Only PDF and DOCX are supported.")

    documents = loader.load()
    logger.info(f"Loaded {len(documents)} pages from {filename}")

    # 2. 初始化 Embedding 模型（使用缓存）
    embeddings = get_embeddings_cached(
        embedding_model_name=embedding_model_name,
        normalize_embeddings=normalize_embeddings,
    )

    # 3. 确保集合存在
    milvus_uri = os.getenv("MILVUS_URI", "http://localhost:19530")
    connection_args = build_milvus_connection_args(milvus_uri)

    ensure_collection(
        collection_name=collection_name,
        dim=embeddings.client.get_sentence_embedding_dimension(),
        drop_if_exists=False,
        connection_args=connection_args,
        index_type="IVF_FLAT",
        index_params={"nlist": 1024},
    )

    # 4. 初始化 Vector Store
    nprobe = int(os.getenv("MILVUS_NPROBE", "32"))
    vector_store = MilvusVectorStore(
        embedding_function=embeddings,
        collection_name=collection_name,
        connection_args=connection_args,
        primary_field="id",
        vector_field="vector",
        text_field="text",
        metadata_field="metadata",
        auto_id=False,
        search_params={"params": {"nprobe": nprobe}, "metric_type": "COSINE"},
    )

    # 5. 文本分块
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=overlap)
    chunks = text_splitter.split_documents(documents)

    logger.info(f"Split into {len(chunks)} chunks")

    # 6. 生成 IDs
    ids = []

    # doc_id 用文件内容 hash，避免同名冲突，也能区分版本
    doc_id = sha1_file(file_path)

    # 生成file_id，用于前端文档链接
    file_id = str(uuid5(NAMESPACE_URL, f"{dept_key}/{filename}"))

    for idx, chunk in enumerate(chunks):
        page = chunk.metadata.get("page", "nil")

        # 每个 chunk 的唯一 id
        chunk_id = f"{doc_id}:{page}:{idx}"
        ids.append(chunk_id)

        # metadata 统一写入（用于过滤/追溯/引用）
        chunk.metadata.update(
            {
                "source": file_path,
                "filename": filename,
                "doc_id": doc_id,
                "page": page,
                "chunk_index": idx,
                "chunk_id": chunk_id,
                "dept_key": dept_key,
                "file_id": file_id,
            }
        )

    # 7. 添加到 Milvus
    vector_store.add_documents(chunks, ids=ids)

    logger.info(f"Document added to Milvus: {filename} with {len(chunks)} chunks")


def delete_document_from_milvus(
    file_path: str,
    dept_key: str,
    filename: str,
    doc_id: str = None,
    collection_name: str = None,
) -> int:
    """从 Milvus 删除文档的所有 chunks

    根据 doc_id（文件内容 SHA1）删除所有相关的向量数据

    Args:
        file_path: 文件路径（用于计算 doc_id）
        dept_key: 部门标识（用于日志）
        filename: 文件名（用于日志）
        doc_id: 文档ID（可选，如果提供则直接使用，否则计算）
        collection_name: 集合名称，默认从环境变量读取

    Returns:
        删除的 chunk 数量

    Raises:
        Exception: Milvus 操作失败

    注意：
        - 如果文件已被删除，doc_id 可能无法计算
        - 此时如果 doc_id 参数未提供，会返回 0
    """
    # 获取集合名称
    if collection_name is None:
        collection_name = os.getenv("MILVUS_COLLECTION_DOC", "knowledge_base_doc")

    logger.info(f"Deleting vector data: dept_key={dept_key}, filename={filename}")

    # 使用提供的 doc_id，或计算 doc_id
    if doc_id is None:
        try:
            doc_id = sha1_file(file_path)
        except Exception as e:
            logger.warning(f"Cannot compute doc_id (file may already be deleted): {e}")
            return 0

    # 确保有 doc_id
    if not doc_id:
        return 0

    # 构建删除表达式：删除所有 doc_id 匹配的 chunks
    # chunk_id 格式：{doc_id}:{page}:{idx}
    # metadata.doc_id 存储了文件的 doc_id
    expr = f'metadata["doc_id"] == "{doc_id}"'

    # 连接 Milvus
    milvus_uri = os.getenv("MILVUS_URI", "http://localhost:19530")
    connection_args = build_milvus_connection_args(milvus_uri)

    from pymilvus import Collection, connections, utility

    connections.connect("default", **connection_args)

    # 检查集合是否存在
    if not utility.has_collection(collection_name):
        logger.info(f"Collection does not exist: {collection_name}")
        return 0

    # 获取集合
    collection = Collection(collection_name)

    # 查询匹配的 chunks
    results = collection.query(
        expr=expr,
        output_fields=["id"],
    )

    if len(results) == 0:
        logger.info(f"No chunks found for doc_id={doc_id}")
        return 0

    # 获取所有 id (chunk_id 存储在 id 字段中)
    ids_to_delete = [r["id"] for r in results]

    # 删除 chunks
    collection.delete(expr=expr)

    logger.info(
        f"Deleted {len(ids_to_delete)} chunks from Milvus: doc_id={doc_id}, dept_key={dept_key}, filename={filename}"
    )

    return len(ids_to_delete)
