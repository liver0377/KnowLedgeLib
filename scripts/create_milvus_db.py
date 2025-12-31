import os
import hashlib
from typing import Optional, Any

from dotenv import load_dotenv
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import Docx2txtLoader, PyPDFLoader
from langchain_community.embeddings import HuggingFaceBgeEmbeddings
from langchain_milvus import Milvus as MilvusVectorStore
from pymilvus import (
    Collection,
    CollectionSchema,
    DataType,
    FieldSchema,
    connections,
    utility,
)

# Load environment variables from the .env file
load_dotenv()

def sha1_file(path: str, buf_size: int = 1024 * 1024) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as f:
        while True:
            b = f.read(buf_size)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def build_milvus_connection_args(uri: str) -> dict[str, Any]:
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
    """Create Milvus collection/index if needed (id/vector/text/metadata only)."""
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
            print(f"Collection `{collection_name}` already exists.")
            return

    fields = [
        FieldSchema(
            name="id",
            dtype=DataType.VARCHAR,
            is_primary=True,
            auto_id=False,
            max_length=128,  
        ),
        FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=dim),
        FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=text_max_length), # 存储chunk原文
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
    print(f"Collection `{collection_name}` ready. Index: {index_type}, metric: {metric}, params: {index_params}")


def create_milvus_db(
    folder_path: str,
    collection_name: str = "knowledge_base",
    drop_if_exists: bool = False,
    chunk_size: int = 2000,
    overlap: int = 500,
    embedding_model_name: str = "BAAI/bge-m3",
    device: Optional[str] = None,
    normalize_embeddings: bool = True,
    nprobe: int = 32,
    index_type: str = "IVF_FLAT",
    index_params: dict[str, Any] = {"nlist": 1024}
):
    """
    Build a Milvus collection using BGE embeddings (default: BAAI/bge-m3)
    and ingest pdf/docx documents from a folder.
    """
    milvus_uri = os.getenv("MILVUS_URI", "http://localhost:19530")
    connection_args: dict = {"uri": milvus_uri}
    if token := os.getenv("MILVUS_TOKEN"):
        connection_args["token"] = token
    if user := os.getenv("MILVUS_USERNAME"):
        connection_args["user"] = user
    if password := os.getenv("MILVUS_PASSWORD"):
        connection_args["password"] = password
    if db_name := os.getenv("MILVUS_DB_NAME"):
        connection_args["db_name"] = db_name
    if os.getenv("MILVUS_TLS", "false").lower() == "true":
        connection_args["secure"] = True

    resolved_device = device or os.getenv("EMBEDDING_DEVICE", "cpu")
    model_kwargs = {"device": resolved_device} if resolved_device else {}

    embeddings = HuggingFaceBgeEmbeddings(
        model_name=embedding_model_name,
        model_kwargs=model_kwargs,
        encode_kwargs={
            "normalize_embeddings": normalize_embeddings,
        },
    )

    # Ensure collection + index exists
    ensure_collection(
        collection_name=collection_name,
        dim=embeddings.client.get_sentence_embedding_dimension(),
        drop_if_exists=drop_if_exists,
        connection_args=connection_args,
        index_type=index_type,
        index_params=index_params
    )

    # Initialize vector store
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

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=overlap)

    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)

        if filename.lower().endswith(".pdf"):
            loader = PyPDFLoader(file_path)
        elif filename.lower().endswith(".docx"):
            loader = Docx2txtLoader(file_path)
        else:
            continue  # Skip unsupported file types

        documents = loader.load()
        chunks = text_splitter.split_documents(documents)

        ids = []

        # doc_id 用文件内容 hash，避免同名冲突，也能区分版本
        doc_id = sha1_file(file_path)

        for idx, chunk in enumerate(chunks):
            page = chunk.metadata.get("page", "nil")

            # 每个 chunk 的唯一 id
            chunk_id = f"{doc_id}:{page}:{idx}"
            ids.append(chunk_id)

            # metadata 统一写入（用于过滤/追溯/引用）
            chunk.metadata.update({
                "source": file_path,
                "filename": filename,
                "doc_id": doc_id,
                "page": page,
                "chunk_index": idx,
            })

        # vector, text, metadata均会在add_documents自动赋值
        vector_store.add_documents(chunks, ids=ids)
        print(f"Document {filename} added with {len(chunks)} chunks.")

    print(f"Milvus collection `{collection_name}` is ready with ingested documents.")
    return vector_store


if __name__ == "__main__":
    folder_path = "./data"

    milvus_store = create_milvus_db(
        folder_path=folder_path,
        collection_name=os.getenv("MILVUS_COLLECTION", "knowledge_base"),
        drop_if_exists=True,
        chunk_size=2000,
        overlap=500,
    )

    retriever = milvus_store.as_retriever(search_kwargs={"k": 3})
    query = "What's my company's mission and values"
    results = retriever.invoke(query)

    for i, doc in enumerate(results, start=1):
        print(f"\n🔹 Result {i}:\n{doc.page_content}\nTags: {doc.metadata}")
