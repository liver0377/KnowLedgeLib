"""
RAGAS 评估脚本 - 用于评估 KB Agent 的 RAG 性能

功能：
1. 从 Langfuse Cloud 拉取 Dataset items
2. 对每个 item 调用 kb_agent.ainvoke()
3. 提取 question/answer/contexts
4. 使用 RAGAS 计算 context_precision / faithfulness / answer_relevancy
5. 将结果上传到 Langfuse Dataset Run

使用：
    python scripts/ragas_eval_kb_agent.py --dataset-name "kb_evaluation"
"""

import asyncio
import os
import logging
from typing import Any
from uuid import uuid4

import click
from dotenv import load_dotenv
from langfuse import Langfuse
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.runnables import RunnableConfig
from ragas import EvaluationDataset, evaluate
from ragas.metrics import (
    context_precision,
    faithfulness,
    answer_relevancy,
)

# 导入项目模块
import sys
from pathlib import Path

# 添加 src 到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agents import get_agent, DEFAULT_AGENT
from core import settings
from core.embeddings import get_cached_embeddings

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def get_ragas_llm():
    """
    获取 RAGAS 评估使用的 LLM

    复用 Langfuse 配置的 qwen-plus 作为 LLM-as-judge
    """
    from langchain_openai import ChatOpenAI

    # 从 settings 获取 LLM 配置
    model_name = getattr(settings, "DEFAULT_MODEL", "qwen-plus")

    # 检查是否为 OpenAI 兼容的模型
    if "qwen" in model_name.lower() or "deepseek" in model_name.lower():
        # 使用 DashScope API（阿里云）
        base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
        api_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("OPENAI_API_KEY")

        if not api_key:
            raise ValueError("DASHSCOPE_API_KEY or OPENAI_API_KEY must be set for RAGAS evaluation")

        return ChatOpenAI(
            model=model_name,
            base_url=base_url,
            api_key=api_key,
            temperature=0.0,
        )
    else:
        # 使用默认 OpenAI API
        return ChatOpenAI(
            model=model_name,
            temperature=0.0,
        )


def get_ragas_embeddings():
    """
    获取 RAGAS 评估使用的 Embedding 模型

    复用项目的 BAAI/bge-m3 模型
    """
    from langchain_huggingface import HuggingFaceEmbeddings

    embeddings = get_cached_embeddings(
        embedding_model_name="BAAI/bge-m3",
        normalize_embeddings=True,
    )

    return embeddings


def extract_data_from_agent_state(state: dict[str, Any], question: str) -> dict[str, Any]:
    """
    从 AgentState 提取 RAGAS 评估所需的数据

    Args:
        state: Agent 返回的 state
        question: 用户输入的问题

    Returns:
        dict: 包含 question, answer, contexts 的字典
    """
    # 提取 answer（最后一条 AIMessage 的 content）
    messages = state.get("messages", [])
    answer = ""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            answer = msg.content
            break

    # 提取 contexts（从 retrieved_documents 提取 content）
    retrieved_docs = state.get("retrieved_documents", [])
    contexts = [doc.get("content", "") for doc in retrieved_docs]

    return {
        "question": question,
        "answer": answer,
        "contexts": contexts,
    }


async def evaluate_single_item(
    item: dict[str, Any],
    agent: Any,
    configurable: dict[str, Any],
    user_id: str,
) -> dict[str, Any] | None:
    """
    评估单个 Dataset item

    Args:
        item: Langfuse Dataset item
        agent: LangGraph agent 实例
        configurable: agent 配置
        user_id: 用户 ID（用于 Langfuse trace）

    Returns:
        dict: 包含评估结果的字典，如果失败返回 None
    """
    item_id = item.get("id")
    question = item.get("input", "")

    if not question:
        logger.warning(f"Item {item_id} has no question, skipping")
        return None

    try:
        # 1. 调用 agent
        config = RunnableConfig(
            configurable={
                **configurable,
                "user_id": user_id,
                "thread_id": str(uuid4()),
            }
        )

        state = await agent.ainvoke(
            input={"messages": [HumanMessage(content=question)]},
            config=config,
        )

        # 2. 提取数据
        data = extract_data_from_agent_state(state, question)

        # 3. 验证数据完整性
        if not data["answer"]:
            logger.warning(f"Item {item_id}: No answer generated, skipping")
            return None

        if not data["contexts"]:
            logger.warning(f"Item {item_id}: No contexts retrieved, skipping")
            return None

        logger.info(f"Item {item_id}: Extracted data successfully")
        logger.info(f"  Question: {question[:100]}...")
        logger.info(f"  Answer: {data['answer'][:100]}...")
        logger.info(f"  Contexts: {len(data['contexts'])} chunks")

        return {
            "item_id": item_id,
            "question": question,
            "answer": data["answer"],
            "contexts": data["contexts"],
        }

    except Exception as e:
        logger.error(f"Item {item_id}: Evaluation failed - {e}")
        return None


async def evaluate_dataset(
    dataset_name: str,
    agent_id: str = DEFAULT_AGENT,
    max_concurrent: int = 5,
    admin_user_id: str = "admin",
):
    """
    评估整个 Dataset

    Args:
        dataset_name: Langfuse Dataset 名称
        agent_id: Agent ID
        max_concurrent: 最大并发数
        admin_user_id: Admin 用户 ID
    """
    # 1. 初始化 Langfuse
    if not settings.LANGFUSE_PUBLIC_KEY or not settings.LANGFUSE_SECRET_KEY:
        raise ValueError("LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY must be set")

    langfuse = Langfuse()

    # 2. 获取 Dataset
    logger.info(f"Fetching dataset: {dataset_name}")
    dataset = langfuse.get_dataset(dataset_name)

    if not dataset:
        logger.error(f"Dataset '{dataset_name}' not found")
        return

    items = dataset.items
    total_items = len(items)

    if total_items == 0:
        logger.warning(f"Dataset '{dataset_name}' is empty")
        return

    logger.info(f"Dataset '{dataset_name}' contains {total_items} items")

    # 3. 初始化 Agent
    agent = get_agent(agent_id)

    # 4. 配置 admin 用户上下文
    configurable = {
        "user_id": admin_user_id,
        "roles": ["admin"],
        "allowed_dept_keys": ["*"],
        "can_use_text2sql": True,
        "text2sql_allowed_databases": ["*"],
    }

    # 5. 并发评估所有 items
    logger.info(f"Starting evaluation with max_concurrent={max_concurrent}")

    semaphore = asyncio.Semaphore(max_concurrent)

    async def process_with_limit(item):
        async with semaphore:
            return await evaluate_single_item(
                item=item,
                agent=agent,
                configurable=configurable,
                user_id=admin_user_id,
            )

    results = await asyncio.gather(
        *[process_with_limit(item) for item in items],
        return_exceptions=False,
    )

    # 6. 过滤成功的结果
    successful_results = [r for r in results if r is not None]
    failed_count = total_items - len(successful_results)

    logger.info(
        f"Evaluation completed: {len(successful_results)}/{total_items} successful, "
        f"{failed_count} skipped"
    )

    if len(successful_results) == 0:
        logger.warning("No successful evaluations, aborting")
        return

    # 7. 构建 RAGAS EvaluationDataset
    evaluation_dataset = EvaluationDataset.from_list(
        [
            {
                "question": r["question"],
                "answer": r["answer"],
                "contexts": r["contexts"],
            }
            for r in successful_results
        ]
    )

    # 8. 初始化 RAGAS 评估器
    logger.info("Initializing RAGAS evaluators")

    llm = get_ragas_llm()
    embeddings = get_ragas_embeddings()

    metrics = [
        context_precision,
        faithfulness,
        answer_relevancy,
    ]

    # 9. 运行 RAGAS 评估
    logger.info("Running RAGAS evaluation...")
    result = evaluate(
        dataset=evaluation_dataset,
        metrics=metrics,
        llm=llm,
        embeddings=embeddings,
        raise_exceptions=False,
    )

    logger.info("RAGAS evaluation completed")

    # 10. 输出结果
    print("\n" + "=" * 80)
    print("RAGAS 评估结果")
    print("=" * 80)
    print(result.to_pandas())
    print("=" * 80 + "\n")

    # 11. 上传到 Langfuse Dataset Run
    run_name = f"ragas_eval_{dataset_name}_{uuid4().hex[:8]}"

    logger.info(f"Creating Langfuse Dataset Run: {run_name}")

    # 创建 Dataset Run
    run = langfuse.create_dataset_run(
        dataset_name=dataset_name,
        name=run_name,
        description=f"RAGAS evaluation for {dataset_name}",
    )

    # 为每个成功的 item 上传分数
    for i, r in enumerate(successful_results):
        item_id = r["item_id"]

        # 获取对应行的评估分数
        row = result.to_pandas().iloc[i]

        try:
            # 上传 context_precision
            run.score(
                item_id=item_id,
                name="context_precision",
                value=float(row["context_precision"]),
                comment=row.get("context_precision_comment", ""),
            )

            # 上传 faithfulness
            run.score(
                item_id=item_id,
                name="faithfulness",
                value=float(row["faithfulness"]),
                comment=row.get("faithfulness_comment", ""),
            )

            # 上传 answer_relevancy
            run.score(
                item_id=item_id,
                name="answer_relevancy",
                value=float(row["answer_relevancy"]),
                comment=row.get("answer_relevancy_comment", ""),
            )

            logger.info(f"Item {item_id}: Scores uploaded successfully")

        except Exception as e:
            logger.warning(f"Item {item_id}: Failed to upload scores - {e}")

    logger.info(f"Dataset Run '{run_name}' completed successfully")
    logger.info(f"View results in Langfuse: {settings.LANGFUSE_HOST}/dataset/{dataset_name}")


@click.command()
@click.option(
    "--dataset-name",
    default="kb_evaluation",
    help="Langfuse Dataset 名称",
)
@click.option(
    "--agent-id",
    default=DEFAULT_AGENT,
    help="Agent ID",
)
@click.option(
    "--max-concurrent",
    default=5,
    help="最大并发数",
)
@click.option(
    "--admin-user-id",
    default="admin",
    help="Admin 用户 ID",
)
def main(
    dataset_name: str,
    agent_id: str,
    max_concurrent: int,
    admin_user_id: str,
):
    """
    RAGAS 评估脚本

    使用示例：
        python scripts/ragas_eval_kb_agent.py --dataset-name "kb_evaluation"
    """
    asyncio.run(
        evaluate_dataset(
            dataset_name=dataset_name,
            agent_id=agent_id,
            max_concurrent=max_concurrent,
            admin_user_id=admin_user_id,
        )
    )


if __name__ == "__main__":
    main()
