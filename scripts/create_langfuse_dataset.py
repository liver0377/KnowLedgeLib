"""
创建 Langfuse Dataset 的辅助脚本

用于快速创建 RAGAS 评估所需的 Dataset 和 items

使用：
    python scripts/create_langfuse_dataset.py --dataset-name "kb_evaluation"

示例：
    # 创建示例 Dataset
    python scripts/create_langfuse_dataset.py --sample --dataset-name "kb_evaluation"

    # 从 JSON 文件创建 items
    python scripts/create_langfuse_dataset.py --json-file scripts/kb_evaluation_questions.json --dataset-name "kb_evaluation"

    # 列出所有 Dataset
    python scripts/create_langfuse_dataset.py --list
"""

import json
import logging
from typing import Any, Iterable

import click
from dotenv import load_dotenv
from langfuse import Langfuse

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def _get_datasets_client(langfuse: Langfuse):
    """
    Langfuse v3 的 API 入口在不同版本/写法里可能叫 client 或 api。
    这里做个兼容：优先用 langfuse.client，其次 langfuse.api
    """
    root = getattr(langfuse, "client", None) or getattr(langfuse, "api", None)
    if root is None:
        raise RuntimeError(
            "Cannot find Langfuse API client. Expected Langfuse().client or Langfuse().api"
        )
    datasets_client = getattr(root, "datasets", None)
    if datasets_client is None:
        raise RuntimeError("Cannot find datasets client at Langfuse().client.datasets / api.datasets")
    return datasets_client


def ensure_dataset_exists(
    langfuse: Langfuse,
    dataset_name: str,
    description: str | None = None,
    metadata: Any | None = None,
) -> None:
    """
    创建 dataset；如果已存在则跳过（不同后端/版本会返回不同异常，这里做宽松处理）
    """
    try:
        langfuse.create_dataset(
            name=dataset_name,
            description=description or f"{dataset_name} - RAG evaluation dataset",
            metadata=metadata,
        )
        logger.info(f"Dataset '{dataset_name}' created")
    except Exception as e:
        # 常见场景：dataset 已存在（409/冲突），这里不让脚本直接挂掉
        logger.warning(
            f"Create dataset '{dataset_name}' failed (maybe already exists). Continue. Error: {e}"
        )


def _load_items_from_json(json_file: str) -> list[dict[str, Any]]:
    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("JSON root must be a list of items")

    # 允许 item 是 dict，且至少有 input / expected_output 其中一个
    items: list[dict[str, Any]] = []
    for idx, raw in enumerate(data):
        if not isinstance(raw, dict):
            raise ValueError(f"Item #{idx} must be an object/dict")
        if "input" not in raw and "expected_output" not in raw:
            raise ValueError(f"Item #{idx} must contain at least 'input' or 'expected_output'")
        items.append(raw)

    return items


def add_items_to_dataset(
    langfuse: Langfuse,
    dataset_name: str,
    items: Iterable[dict[str, Any]],
) -> int:
    """
    v3 正确方式：用 langfuse.create_dataset_item(...) 往 dataset 里加 item
    """
    count = 0
    for idx, item in enumerate(items):
        try:
            langfuse.create_dataset_item(
                dataset_name=dataset_name,
                input=item.get("input"),
                expected_output=item.get("expected_output"),
                metadata=item.get("metadata"),
            )
            count += 1
        except Exception as e:
            logger.error(f"Failed to add item #{idx} to dataset '{dataset_name}': {e}")
            raise
    return count


def create_dataset_from_json(
    dataset_name: str,
    json_file: str,
    description: str | None = None,
):
    """
    从 JSON 文件创建 Langfuse Dataset

    JSON 文件格式（示例）：
    [
        {
            "input": "用户问题",
            "expected_output": "预期答案",
            "metadata": {"key": "value"}
        },
        ...
    ]
    """
    langfuse = Langfuse()

    ensure_dataset_exists(langfuse, dataset_name, description)

    items = _load_items_from_json(json_file)
    added = add_items_to_dataset(langfuse, dataset_name, items)
    logger.info(f"Added {added} items to dataset '{dataset_name}'")


def create_sample_dataset(dataset_name: str):
    """
    创建示例 Dataset（用于测试）
    """
    langfuse = Langfuse()

    ensure_dataset_exists(
        langfuse,
        dataset_name,
        description=f"{dataset_name} - KB Agent RAG evaluation sample dataset",
    )

    sample_items = [
        {
            "input": "什么是 CKafka？",
            "expected_output": "CKafka 是腾讯云提供的分布式消息队列服务",
            "metadata": {"category": "产品介绍"},
        },
        {
            "input": "CKafka 支持哪些消息协议？",
            "expected_output": "CKafka 支持 Kafka 协议、MQTT 协议",
            "metadata": {"category": "功能特性"},
        },
        {
            "input": "如何使用 CKafka？",
            "expected_output": "可以通过腾讯云控制台、API、SDK 等方式使用 CKafka",
            "metadata": {"category": "使用指南"},
        },
        {
            "input": "CKafka 的计费方式是什么？",
            "expected_output": "CKafka 支持按量计费和包年包月两种计费方式",
            "metadata": {"category": "计费说明"},
        },
        {
            "input": "CKafka 和 RabbitMQ 有什么区别？",
            "expected_output": "CKafka 是分布式消息队列服务，支持高吞吐、高可用；RabbitMQ 是消息中间件，适合企业级应用",
            "metadata": {"category": "产品对比"},
        },
    ]

    added = add_items_to_dataset(langfuse, dataset_name, sample_items)
    logger.info(f"Added {added} sample items to dataset '{dataset_name}'")


def list_datasets():
    """列出所有 Dataset（v3：通过 client/api 的 datasets.list 分页获取）"""
    langfuse = Langfuse()
    datasets_client = _get_datasets_client(langfuse)

    all_datasets = []
    page = 1
    limit = 50

    while True:
        result = datasets_client.list(page=page, limit=limit)

        data = getattr(result, "data", None) or []
        all_datasets.extend(data)

        meta = getattr(result, "meta", None)
        total_pages = None
        if meta is not None:
            for attr in ("total_pages", "total_pagses", "totalPages", "totalPagses"):
                if hasattr(meta, attr):
                    total_pages = getattr(meta, attr)
                    break

        # 优先用 total_pages 判断；拿不到就用“本页数量 < limit”判断结束
        if total_pages is not None:
            if page >= int(total_pages):
                break
        else:
            if len(data) < limit:
                break

        page += 1

    if not all_datasets:
        logger.info("No datasets found")
        return

    logger.info(f"Found {len(all_datasets)} dataset(s):")
    for ds in all_datasets:
        name = getattr(ds, "name", "<unknown>")
        desc = getattr(ds, "description", None) or "No description"
        logger.info(f"  - {name}: {desc}")


@click.command()
@click.option("--dataset-name", default="kb_evaluation", help="Dataset 名称")
@click.option("--json-file", default=None, help="从 JSON 文件创建 items")
@click.option("--description", default=None, help="Dataset 描述")
@click.option("--sample", is_flag=True, help="创建示例 Dataset")
@click.option("--list", "list_flag", is_flag=True, help="列出所有 Dataset")
def main(
    dataset_name: str,
    json_file: str | None,
    description: str | None,
    sample: bool,
    list_flag: bool,
):
    if list_flag:
        list_datasets()
        return

    if sample:
        create_sample_dataset(dataset_name)
        return

    if json_file:
        create_dataset_from_json(dataset_name, json_file, description)
        return

    logger.error("Please specify either --sample or --json-file. Use --help to see usage examples.")


if __name__ == "__main__":
    main()
