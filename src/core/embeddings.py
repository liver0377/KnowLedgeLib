"""
统一的嵌入模型管理模块
提供带缓存的嵌入模型实例，避免重复加载和下载
强制使用本地 HuggingFace 缓存，避免联网
"""

import logging
import os
import threading
from typing import Optional

from langchain_huggingface import HuggingFaceEmbeddings

logger = logging.getLogger(__name__)

# ============== 全局缓存变量 ==============
_embeddings_cache: Optional[HuggingFaceEmbeddings] = None
_embeddings_cache_key: Optional[str] = None
_embeddings_lock = threading.Lock()


def _setup_huggingface_cache():
    """配置 HuggingFace 本地缓存环境变量

    强制使用本地缓存目录，避免联网下载模型
    """
    cache_dir = os.getenv("HF_HOME", ".hf_cache")

    # 设置绝对路径（如果提供的是相对路径）
    if not os.path.isabs(cache_dir):
        cache_dir = os.path.abspath(cache_dir)

    # 确保缓存目录存在
    os.makedirs(cache_dir, exist_ok=True)

    # 设置 HuggingFace 环境变量
    os.environ["HF_HOME"] = cache_dir
    os.environ["HUGGINGFACE_HUB_CACHE"] = os.path.join(cache_dir, "hub")
    os.environ["TRANSFORMERS_CACHE"] = os.path.join(cache_dir, "transformers")

    logger.info(f"HuggingFace cache configured: {cache_dir}")
    logger.info(f"  HF_HOME: {os.environ['HF_HOME']}")
    logger.info(f"  HUGGINGFACE_HUB_CACHE: {os.environ['HUGGINGFACE_HUB_CACHE']}")
    logger.info(f"  TRANSFORMERS_CACHE: {os.environ['TRANSFORMERS_CACHE']}")

    return cache_dir


def _should_reload_embeddings(
    embedding_model_name: str,
    device: str,
    normalize_embeddings: bool,
) -> bool:
    """检查是否需要重新加载 Embedding 模型

    如果模型配置发生变化，需要重新加载缓存

    Args:
        embedding_model_name: 模型名称
        device: 运行设备
        normalize_embeddings: 是否归一化

    Returns:
        True 表示需要重新加载
    """
    global _embeddings_cache_key

    if _embeddings_cache is None:
        return True

    new_key = f"{embedding_model_name}:{device}:{normalize_embeddings}"
    if _embeddings_cache_key != new_key:
        logger.info(f"Embedding config changed, reloading: {_embeddings_cache_key} -> {new_key}")
        return True

    return False


def get_cached_embeddings(
    embedding_model_name: str = "BAAI/bge-m3",
    device: Optional[str] = None,
    normalize_embeddings: bool = True,
) -> HuggingFaceEmbeddings:
    """获取缓存的 Embedding 模型实例

    首次调用时加载模型，后续调用返回缓存的实例。
    强制使用 HuggingFace 本地缓存，避免重复下载和联网。

    Args:
        embedding_model_name: 模型名称（HuggingFace Hub 上的模型）
        device: 运行设备（cpu/cuda/mps等），None则从环境变量读取
        normalize_embeddings: 是否对嵌入向量进行归一化

    Returns:
        HuggingFaceEmbeddings 实例（可能来自缓存）
    """
    global _embeddings_cache, _embeddings_cache_key, _embeddings_lock

    resolved_device = device or os.getenv("EMBEDDING_DEVICE", "cpu")
    model_kwargs = {"device": resolved_device} if resolved_device else {}

    if _should_reload_embeddings(embedding_model_name, resolved_device, normalize_embeddings):
        with _embeddings_lock:
            if _should_reload_embeddings(
                embedding_model_name, resolved_device, normalize_embeddings
            ):
                logger.info(
                    f"Loading embedding model (first time or config changed): {embedding_model_name}"
                )
                logger.info(f"Model will run on device: {resolved_device}")

                # 配置 HuggingFace 本地缓存（强制使用，避免联网）
                cache_dir = _setup_huggingface_cache()

                # 使用本地缓存目录
                _embeddings_cache = HuggingFaceEmbeddings(
                    model_name=embedding_model_name,
                    model_kwargs=model_kwargs,
                    encode_kwargs={"normalize_embeddings": normalize_embeddings},
                    cache_folder=cache_dir,
                )

                _embeddings_cache_key = (
                    f"{embedding_model_name}:{resolved_device}:{normalize_embeddings}"
                )
                logger.info("Embedding model loaded and cached in memory")
                logger.info("All HuggingFace operations will use local cache (no network access)")
    else:
        logger.debug("Using cached embedding model from memory")

    # 确保返回有效实例（类型安全）
    assert _embeddings_cache is not None, "Embedding cache should be loaded at this point"
    return _embeddings_cache


def clear_embeddings_cache():
    """清除嵌入模型缓存

    用于测试或需要强制重新加载模型的场景
    """
    global _embeddings_cache, _embeddings_cache_key, _embeddings_lock

    with _embeddings_lock:
        if _embeddings_cache is not None:
            logger.info("Clearing embeddings cache from memory")
            _embeddings_cache = None
            _embeddings_cache_key = None
