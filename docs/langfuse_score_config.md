# Langfuse 评分项（Score Config）汇总

> 本文档标记了所有评分指标的实现状态、评估类型和适用场景
> - **✅ 已实现**: 评估器已创建并集成
> - **🚀 可自动化**: 可以通过代码自动评估
> - **👤 需人工**: 需要人工标注或审核
> - **暂未实现**: 尚未实现，计划中



## 一、RAG / 知识库检索（KB）

### 1) rag_retrieval_problem
- **评估类型**: 👤 需人工标注
- **实现方式**: 需要专家分析检索流程，分类问题根因
- **实现状态**: 暂未实现
- **数据类型**: CATEGORICAL（枚举）
- **可选值（6项）**:
  - `query_mismatch`
  - `chunking_issue`
  - `embedding_issue`
  - `duplicate_or_redundant`
  - `metadata_filter_missing`
  - `other`

---

### 2) rag_top1_is_best
- **评估类型**: 👤 需人工标注
- **实现方式**: 需要人工评估检索结果排序质量
- **实现状态**: 暂未实现
- **数据类型**: BOOLEAN（是/否）

---

### 3) rag_context_sufficiency
- **评估类型**: 👤 需人工标注
- **实现方式**: 需要人工评估检索结果是否足够支撑回答
- **实现状态**: 暂未实现
- **数据类型**: BOOLEAN（是/否）

---

### 4) rag_retrieved_relevance 🚀
- **评估类型**: ✅ 自动化 - LLM-as-a-Judge
- **实现方式**: 使用 LLM 评估检索结果与问题的相关性
- **实现状态**: ✅ 已实现 (`RetrievalRelevanceEvaluator`)
- **数据类型**: NUMERIC（数值）
- **取值范围**: 1–5
- **推荐模型**: qwen-plus
- **适用场景**: RAG 问答
- **评分标准**:
  - 1: 几乎无关
  - 2: 少量沾边，大多噪声
  - 3: 主题相关但关键细节缺失
  - 4: 大多相关，少量噪声
  - 5: 高度相关，覆盖关键点

---

### 5) rag_issue_type
- **评估类型**: 👤 需人工标注
- **实现方式**: 需要人工分类问题类型
- **实现状态**: 暂未实现
- **数据类型**: CATEGORICAL（枚举）

---

### 6) rag_needs_clarification 🚀
- **评估类型**: ✅ 自动化 - 规则检测
- **实现方式**: 正则表达式匹配反问和不确定表达
- **实现状态**: ✅ 已实现 (`NeedsClarificationEvaluator`)
- **数据类型**: BOOLEAN（是/否）
- **适用场景**: RAG 问答
- **检测模式**:
  - "需要...知道/确认/了解"
  - "是否...可以/能够/需要"
  - 反问句式
  - 不确定表达

---

### 7) rag_answer_helpfulness 🚀
- **评估类型**: ✅ 自动化 - LLM-as-a-Judge
- **实现方式**: 使用 LLM 评估回答的有用性和可执行性
- **实现状态**: ✅ 已实现 (`AnswerHelpfulnessEvaluator`)
- **数据类型**: NUMERIC（数值）
- **取值范围**: 1–5
- **推荐模型**: qwen-plus
- **适用场景**: RAG 问答
- **评分标准**:
  - 1: 毫无帮助，答非所问
  - 2: 提供少量信息但不完整
  - 3: 提供基本信息但缺乏深度
  - 4: 提供有用的答案但需补充
  - 5: 完全满足需求，可直接执行

---

### 8) rag_groundedness 🚀
- **评估类型**: ✅ 自动化 - LLM-as-a-Judge
- **实现方式**: 使用 LLM 评估是否存在编造或与引用矛盾
- **实现状态**: ✅ 已实现 (`GroundednessEvaluator`)
- **数据类型**: NUMERIC（数值）
- **取值范围**: 1–5
- **推荐模型**: qwen-plus
- **适用场景**: RAG 问答
- **评分标准**:
  - 1: 完全编造或与引用矛盾
  - 2: 大量编造，缺乏引用支持
  - 3: 部分内容无依据
  - 4: 基本有据可查，少量超出
  - 5: 严格基于引用，无编造

---

### 9) rag_citation_present ✅
- **评估类型**: ✅ 自动化 - 规则检测
- **实现方式**: 正则表达式检测 Markdown 引用链接
- **实现状态**: ✅ 已实现 (`CitationEvaluator`)
- **数据类型**: BOOLEAN（是/否）
- **适用场景**: 知识库查询
- **检测模式**: `\[[^\]]+\]\(/kb/files/[0-9a-f\-]+/download\)`

---

### 10) rag_citation_correct 🚀
- **评估类型**: ✅ 自动化 - LLM-as-a-Judge
- **实现方式**: 使用 LLM 评估引用是否真实有效且支持回答
- **实现状态**: ✅ 已实现 (`CitationCorrectnessEvaluator`)
- **数据类型**: BOOLEAN（是/否）
- **适用场景**: RAG 问答
- **评估维度**:
  - 引用格式是否正确
  - 引用是否真实存在
  - 引用内容是否支持回答结论

## 二、Text2SQL

### 1) execution_success
- **评估类型**: ✅ 自动化 - 执行结果
- **实现方式**: 捕获 SQL 执行结果
- **实现状态**: ✅ 已实现 (`ExecutionSuccessEvaluator`)
- **数据类型**: BOOLEAN（是/否）
- **说明**: SQL 能否在目标库/沙箱里成功执行
- **评分规则**:
  - 执行成功 (score=1.0): sql_exec_error 为空
  - 执行失败 (score=0.0): sql_exec_error 有值

---

### 2) result_correct
- **评估类型**: 🚀 可自动化 - LLM-as-a-Judge
- **实现方式**: 使用 LLM 评估查询结果是否符合用户意图
- **实现状态**: 暂未实现
- **数据类型**: BOOLEAN（是/否）

---

### 3) uses_correct_tables
- **评估类型**: 👤 需人工标注
- **实现方式**: 需要评估表选择是否正确，需要业务知识
- **实现状态**: 暂未实现
- **数据类型**: BOOLEAN（是/否）

---

### 4) needs_clarification (Text2SQL)
- **评估类型**: 👤 需人工标注
- **实现方式**: 需要判断问题是否清晰，主观性强
- **实现状态**: 暂未实现
- **数据类型**: BOOLEAN（是/否）

---

### 5) sql_error_type
- **评估类型**: ✅ 自动化 - 异常捕获
- **实现方式**: 捕获 SQL 执行异常，解析错误信息
- **实现状态**: 暂未实现
- **数据类型**: CATEGORICAL（枚举）

---

### 6) safety_risk 🚀
- **评估类型**: ✅ 自动化 - 规则检测
- **实现方式**: 正则表达式检测危险操作和全表扫描
- **实现状态**: ✅ 已实现 (`SafetyRiskEvaluator`)
- **数据类型**: CATEGORICAL（枚举）
- **适用场景**: Text2SQL
- **检测维度**:
  - `none`: 无风险 (score=0.0)
  - `pii_risk`: 敏感个人信息 (score=1.0)
  - `write_operation`: 写操作风险 (score=2.0)
  - `broad_scan`: 全表扫描风险 (score=3.0)
  - `policy_violation`: 政策违规 (score=4.0)

---

### 7) sql_readability
- **评估类型**: 🚀 可自动化 - LLM-as-a-Judge
- **实现方式**: 使用 LLM 评估 SQL 的可读性和规范性
- **实现状态**: 暂未实现
- **数据类型**: NUMERIC（数值）
- **取值范围**: 1–5

---

### 8) efficiency
- **评估类型**: 🚀 可自动化 - LLM-as-a-Judge
- **实现方式**: 使用 LLM 评估查询性能和复杂度
- **实现状态**: 暂未实现
- **数据类型**: NUMERIC（数值）
- **取值范围**: 1–5

---

## 总结

### ✅ 已实现评估器

| 评估器 | 类型 | 适用场景 | 文件 |
|--------|------|----------|------|
| `rag_citation_present` | 规则检测 | RAG | `citation_evaluator.py` |
| `rag_needs_clarification` | 规则检测 | RAG | `needs_clarification_evaluator.py` |
| `safety_risk` | 规则检测 | SQL | `safety_risk_evaluator.py` |
| `execution_success` | 执行结果 | SQL | `execution_success_evaluator.py` |
| `rag_citation_correct` | LLM-as-a-Judge | RAG | `citation_correctness_evaluator.py` |
| `rag_retrieved_relevance` | LLM-as-a-Judge | RAG | `retrieval_relevance_evaluator.py` |
| `rag_answer_helpfulness` | LLM-as-a-Judge | RAG | `answer_helpfulness_evaluator.py` |
| `rag_groundedness` | LLM-as-a-Judge | RAG | `groundedness_evaluator.py` |

### 🚀 可实现但未实现

| 评估器 | 类型 | 优先级 | 难度 |
|--------|------|--------|--------|
| `sql_readability` | LLM | 中 | 中 |
| `result_correct` | LLM | 中 | 高 |
| `sql_error_type` | 异常捕获 | 中 | 低 |

### 👤 需人工评估

| 评估器 | 原因 |
|--------|------|
| `rag_retrieval_problem` | 需要专家分析检索流程 |
| `rag_top1_is_best` | 需要人工标注正确答案 |
| `rag_context_sufficiency` | 主观性强，需要人工判断 |
| `rag_issue_type` | 需要人工分类问题类型 |
| `uses_correct_tables` | 需要业务知识评估 |
| `needs_clarification` (SQL) | 需要人工判断问题清晰度 |

---

## 实现参考

- **评估器基类**: `src/evaluation/base.py`
- **评估管理器**: `src/evaluation/manager.py`
- **RAG 评估器**: `src/agents/knowledge_base_agent/nodes_doc.py`
- **系统评估文档**: `docs/系统评估.md`
