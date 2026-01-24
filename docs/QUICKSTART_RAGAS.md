# RAGAS 评估 - 快速开始指南

本文档帮助您快速开始使用 RAGAS 评估脚本。

## 步骤 1: 安装依赖

```bash
# 安装 ragas 依赖
uv sync

# 或使用 pip
pip install ragas>=0.2.0 click
```

## 步骤 2: 配置环境变量

确保 `.env` 文件中配置以下变量：

```bash
# Langfuse 配置（必需）
LANGFUSE_PUBLIC_KEY=pk-xxxxxxxx
LANGFUSE_SECRET_KEY=sk-xxxxxxxx
LANGFUSE_HOST=https://cloud.langfuse.com

# LLM 配置（用于 RAGAS 评估器）
# 使用 Qwen/DashScope:
DASHSCOPE_API_KEY=sk-dbc3bdc15fed4fb8bd875b1ba87ecb41

# 或使用 OpenAI:
OPENAI_API_KEY=sk-xxxxxxxx

# Milvus 配置（用于 agent 调用）
MILVUS_URI=http://localhost:19530
MILVUS_COLLECTION_DOC=knowledge_base_doc
```

## 步骤 3: 创建 Langfuse Dataset

### 方式 1: 使用脚本创建（推荐）

```bash
# 创建示例 Dataset（包含 10 个 CKafka 相关问题）
python scripts/create_langfuse_dataset.py --sample --dataset-name "kb_evaluation"
```

### 方式 2: 使用 JSON 文件创建

```bash
# 使用提供的示例 JSON 文件
python scripts/create_langfuse_dataset.py \
    --json-file scripts/kb_evaluation_questions.json \
    --dataset-name "kb_evaluation"
```

### 方式 3: 在 Langfuse UI 中手动创建

1. 访问 https://cloud.langfuse.com
2. 进入 "Datasets" 页面
3. 点击 "Create Dataset"
4. 输入名称 `kb_evaluation`
5. 手动添加 items

## 步骤 4: 运行 RAGAS 评估

```bash
# 基本用法
python scripts/ragas_eval_kb_agent.py --dataset-name "kb_evaluation"

# 高级用法
python scripts/ragas_eval_kb_agent.py \
    --dataset-name "kb_evaluation" \
    --max-concurrent 5 \
    --admin-user-id "admin"
```

## 步骤 5: 查看结果

### 控制台输出

脚本会输出评估结果的表格：

```
================================================================================
RAGAS 评估结果
================================================================================
   context_precision  faithfulness  answer_relevancy
0           0.8500        0.9000            0.8800
1           0.7800        0.8500            0.8200
...
================================================================================
```

### Langfuse Cloud

1. 访问 https://cloud.langfuse.com/dataset/kb_evaluation
2. 查看自动创建的 Dataset Run（如 `ragas_eval_kb_evaluation_xxx`）
3. 点击查看每个 item 的详细分数

## 常见问题

### Q: 如何添加自定义评估问题？

**A**: 编辑 `scripts/kb_evaluation_questions.json` 文件，添加您的问题，然后重新创建 Dataset：

```bash
python scripts/create_langfuse_dataset.py \
    --json-file scripts/kb_evaluation_questions.json \
    --dataset-name "kb_evaluation"
```

### Q: 如何提高评估速度？

**A**: 增加 `--max-concurrent` 参数：

```bash
python scripts/ragas_eval_kb_agent.py --max-concurrent 10
```

**注意**: 并发数过高可能触发 API 限流，建议从 5 开始逐步调整。

### Q: 如何只评估部分 items？

**A**: 在 Langfuse UI 中创建新的 Dataset，只包含需要评估的 items，然后指定新的 dataset-name。

### Q: 评估失败怎么办？

**A**: 检查日志中的错误信息，常见原因：

1. **Langfuse 连接失败**: 检查 `LANGFUSE_PUBLIC_KEY` 和 `LANGFUSE_SECRET_KEY`
2. **LLM API 调用失败**: 检查 `DASHSCOPE_API_KEY` 或 `OPENAI_API_KEY`
3. **Milvus 连接失败**: 检查 `MILVUS_URI` 和 Milvus 服务状态
4. **无数据**: 确保 Milvus 中有相关的文档数据

### Q: 如何查看每个 item 的详细评估说明？

**A**: 在 Langfuse Cloud 中，点击 Dataset Run，然后点击具体 item，可以看到每个分数的 `comment` 字段，包含评估器的详细说明。

## 下一步

- [ ] 根据评估结果优化检索策略（调整 Milvus 搜索参数）
- [ ] 优化系统提示词（提高回答忠实度）
- [ ] 添加更多评估问题到 Dataset
- [ ] 将评估集成到 CI/CD 流程

## 相关文档

- [RAGAS 评估脚本使用指南](./README_RAGAS_EVAL.md)
- [RAG 检索文档](../docs/RAG检索.md)
- [Langfuse Dataset 文档](https://langfuse.com/docs/datasets)
