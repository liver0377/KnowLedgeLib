# RAGAS 评估脚本使用指南

## 功能说明

`scripts/ragas_eval_kb_agent.py` 是一个用于评估 KB Agent RAG 性能的自动化脚本。

### 核心功能

1. **数据获取**: 从 Langfuse Cloud 拉取 Dataset items
2. **Agent 调用**: 对每个 item 调用 `kb_agent.ainvoke()`
3. **数据提取**: 从 AgentState 提取 `question`/`answer`/`contexts`
4. **RAGAS 评估**: 计算三个核心指标
   - `context_precision`: 检索的文档与问题相关性
   - `faithfulness`: 回答是否基于检索的文档
   - `answer_relevancy`: 回答是否与问题相关
5. **结果上传**: 将评估结果上传到 Langfuse Dataset Run

## 前置条件

### 1. 安装依赖

```bash
# 安装 ragas 依赖
uv sync

# 或使用 pip
pip install ragas>=0.2.0
```

### 2. 环境变量配置

确保 `.env` 文件中配置以下变量：

```bash
# Langfuse 配置（必需）
LANGFUSE_PUBLIC_KEY=pk-xxxxxxxx
LANGFUSE_SECRET_KEY=sk-xxxxxxxx
LANGFUSE_HOST=https://cloud.langfuse.com

# LLM 配置（用于 RAGAS 评估器）
# 如果使用 Qwen/DashScope:
DASHSCOPE_API_KEY=sk-xxxxxxxx

# 或使用 OpenAI:
OPENAI_API_KEY=sk-xxxxxxxx

# Embedding 模型配置（复用项目配置）
EMBEDDING_MODEL_NAME=BAAI/bge-m3
EMBEDDING_DEVICE=cpu
NORMALIZE_EMBEDDINGS=true

# Milvus 配置（用于 agent 调用）
MILVUS_URI=http://localhost:19530
MILVUS_COLLECTION_DOC=knowledge_base_doc
```

### 3. 创建 Langfuse Dataset

在 Langfuse Cloud 中创建 Dataset，命名为 `kb_evaluation`。

#### 添加 Dataset Items

每个 item 需要包含以下字段：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `input` | string | 是 | 用户问题（如 "什么是 CKafka？"） |
| `expected_output` | string | 否 | 预期答案（可选，用于人工评估） |
| `metadata` | object | 否 | 额外的元数据 |

示例：

```python
# 使用 Langfuse SDK 创建 Dataset
from langfuse import Langfuse

langfuse = Langfuse()

dataset = langfuse.create_dataset(
    name="kb_evaluation",
    description="KB Agent RAG 评估数据集",
)

# 添加 items
dataset.create_item(
    input="什么是 CKafka？",
    expected_output="CKafka 是腾讯云提供的分布式消息队列服务...",
    metadata={"category": "产品介绍"},
)

dataset.create_item(
    input="CKafka 支持哪些消息协议？",
    expected_output="CKafka 支持 Kafka 协议、MQTT 协议...",
    metadata={"category": "功能特性"},
)
```

或在 Langfuse UI 中手动添加：
1. 访问 https://cloud.langfuse.com
2. 进入 "Datasets" 页面
3. 点击 "Create Dataset"
4. 输入名称 `kb_evaluation`
5. 添加 items

## 使用方法

### 基本用法

```bash
python scripts/ragas_eval_kb_agent.py --dataset-name "kb_evaluation"
```

### 高级选项

```bash
# 指定 Agent ID
python scripts/ragas_eval_kb_agent.py \
    --dataset-name "kb_evaluation" \
    --agent-id "kb_agent"

# 设置并发数（默认 5）
python scripts/ragas_eval_kb_agent.py \
    --dataset-name "kb_evaluation" \
    --max-concurrent 10

# 指定 admin 用户 ID
python scripts/ragas_eval_kb_agent.py \
    --dataset-name "kb_evaluation" \
    --admin-user-id "admin"
```

### 命令行参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--dataset-name` | `kb_evaluation` | Langfuse Dataset 名称 |
| `--agent-id` | `kb_agent` | Agent ID |
| `--max-concurrent` | `5` | 最大并发数 |
| `--admin-user-id` | `admin` | Admin 用户 ID |

## 输出说明

### 控制台输出

脚本运行时会输出详细的日志信息：

```
2025-01-23 10:00:00 - INFO - Fetching dataset: kb_evaluation
2025-01-23 10:00:01 - INFO - Dataset 'kb_evaluation' contains 10 items
2025-01-23 10:00:01 - INFO - Starting evaluation with max_concurrent=5
2025-01-23 10:00:05 - INFO - Item xxx: Extracted data successfully
2025-01-23 10:00:05 - INFO -   Question: 什么是 CKafka？...
2025-01-23 10:00:05 - INFO -   Answer: CKafka 是腾讯云提供的分布式消息队列服务...
2025-01-23 10:00:05 - INFO -   Contexts: 5 chunks
...
2025-01-23 10:02:00 - INFO - Evaluation completed: 10/10 successful, 0 skipped
2025-01-23 10:02:00 - INFO - Running RAGAS evaluation...
2025-01-23 10:05:00 - INFO - RAGAS evaluation completed

================================================================================
RAGAS 评估结果
================================================================================
   context_precision  faithfulness  answer_relevancy
0           0.8500        0.9000            0.8800
1           0.7800        0.8500            0.8200
...
================================================================================

2025-01-23 10:05:00 - INFO - Creating Langfuse Dataset Run: ragas_eval_kb_evaluation_xxx
2025-01-23 10:05:05 - INFO - Item xxx: Scores uploaded successfully
...
2025-01-23 10:05:30 - INFO - Dataset Run 'ragas_eval_kb_evaluation_xxx' completed successfully
```

### Langfuse Cloud 结果

评估完成后，结果会自动上传到 Langfuse Cloud：

1. 访问 Dataset 页面：`https://cloud.langfuse.com/dataset/kb_evaluation`
2. 查看自动创建的 Dataset Run（如 `ragas_eval_kb_evaluation_xxx`）
3. 每个成功的 item 会有三个分数：
   - `context_precision`
   - `faithfulness`
   - `answer_relevancy`

每个分数都包含：
- `value`: 分数值（0.0 ~ 1.0）
- `comment`: 评估器生成的说明（如 "All relevant contexts were retrieved"）

## 评估指标说明

### Context Precision（上下文精度）

**定义**: 检索到的文档中与问题相关部分的比例

**评分范围**: 0.0 ~ 1.0
- `1.0`: 所有检索到的文档都与问题相关
- `0.0`: 没有检索到相关文档

**含义**: 评估检索器的准确性，越高表示检索越精准

### Faithfulness（忠实度）

**定义**: 回答中基于检索文档的陈述比例

**评分范围**: 0.0 ~ 1.0
- `1.0`: 回答完全基于检索的文档
- `0.0`: 回答与检索的文档无关

**含义**: 评估回答的可靠性，越高表示回答越不"产生幻觉"

### Answer Relevancy（答案相关性）

**定义**: 回答与问题的相关程度

**评分范围**: 0.0 ~ 1.0
- `1.0`: 回答与问题高度相关
- `0.0`: 回答与问题无关

**含义**: 评估回答的针对性，越高表示回答越符合问题意图

## 错误处理

### 跳过策略

脚本会自动跳过以下情况的 items：

1. **无输入**: item 没有 `input` 字段
2. **无回答**: agent 返回的 state 中没有 AIMessage
3. **无上下文**: 没有检索到任何文档
4. **评估失败**: agent 调用或数据提取出错

跳过的 items 会在日志中记录，不会上传到 Langfuse。

### 常见问题

#### 1. Dataset 不存在

```
ERROR - Dataset 'kb_evaluation' not found
```

**解决方案**: 先在 Langfuse Cloud 中创建 Dataset

#### 2. Langfuse 连接失败

```
ValueError: LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY must be set
```

**解决方案**: 检查 `.env` 文件中的 Langfuse 配置

#### 3. LLM API 调用失败

```
ValueError: DASHSCOPE_API_KEY or OPENAI_API_KEY must be set for RAGAS evaluation
```

**解决方案**: 检查 `.env` 文件中的 API Key 配置

#### 4. 所有 items 都被跳过

```
INFO - Evaluation completed: 0/10 successful, 10 skipped
WARNING - No successful evaluations, aborting
```

**可能原因**:
- Milvus 没有数据
- Agent 路由失败（如所有问题都被路由到 text2sql）
- 检索器配置错误

**解决方案**: 检查日志中的详细信息，确认失败原因

## 性能优化

### 并发控制

使用 `--max-concurrent` 参数控制并发数：

```bash
# 低并发（适合 API 限流较严格的情况）
python scripts/ragas_eval_kb_agent.py --max-concurrent 2

# 高并发（适合 API 配额充足的情况）
python scripts/ragas_eval_kb_agent.py --max-concurrent 10
```

**建议**:
- 开发环境: `max-concurrent=2`
- 测试环境: `max-concurrent=5`
- 生产评估: `max-concurrent=10`

## 集成到 CI/CD

可以将评估脚本集成到 CI/CD 流程中：

```yaml
# .github/workflows/ragas_eval.yml
name: RAGAS Evaluation

on:
  push:
    branches: [main]

jobs:
  evaluate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: |
          pip install uv
          uv sync

      - name: Run RAGAS evaluation
        env:
          LANGFUSE_PUBLIC_KEY: ${{ secrets.LANGFUSE_PUBLIC_KEY }}
          LANGFUSE_SECRET_KEY: ${{ secrets.LANGFUSE_SECRET_KEY }}
          DASHSCOPE_API_KEY: ${{ secrets.DASHSCOPE_API_KEY }}
        run: |
          python scripts/ragas_eval_kb_agent.py \
            --dataset-name "kb_evaluation" \
            --max-concurrent 5
```

## 注意事项

1. **成本**: RAGAS 评估使用 LLM-as-judge，会产生 API 调用费用
2. **时间**: 评估时间取决于 Dataset items 数量和并发设置
3. **权限**: 确保使用的用户（默认 admin）有访问所有文档的权限
4. **数据一致性**: 确保 Milvus 中的数据与 Langfuse Dataset 中的问题相关

## 相关文档

- [RAGAS 官方文档](https://docs.ragas.io/)
- [Langfuse Dataset 文档](https://langfuse.com/docs/datasets)
- [项目 RAG 检索文档](../docs/RAG检索.md)
