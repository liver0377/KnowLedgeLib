# RAG 检索系统文档

## 目录

- [一、系统架构](#一系统架构)
- [二、核心组件](#二核心组件)
- [三、Milvus 配置详解](#三milvus-配置详解)
- [四、权限控制](#四权限控制)
- [五、文档导入流程](#五文档导入流程)
- [六、嵌入模型管理](#六嵌入模型管理)
- [七、评估机制](#七评估机制)
- [八、完整流程图](#八完整流程图)
- [九、系统提示词](#九系统提示词)
- [十、环境变量配置](#十环境变量配置)

---

## 一、系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    RAG 检索系统架构                              │
└─────────────────────────────────────────────────────────────────┘

┌──────────────┐     ┌──────────────────┐     ┌─────────────┐
│   前端       │────>│   后端 Service  │────>│  LangGraph  │
│   (Vue)      │     │   (FastAPI)     │     │  Agent      │
└──────────────┘     └──────────────────┘     └─────────────┘
                                                     │
                                                     ▼
              ┌──────────────────────────────────────────┐
              │         知识库检索流程                     │
              └──────────────────────────────────────────┘
                              │
         ┌────────────────────┼────────────────────┐
         ▼                    ▼                    ▼
   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
   │ 权限过滤    │    │ Milvus 检索 │    │ 文档增强    │
   │ dept_key   │    │ 向量搜索    │    │ 提示词      │
   └─────────────┘    └─────────────┘    └─────────────┘
                            │
                            ▼
                     ┌─────────────┐
                     │ Milvus 向量 │
                     │   数据库    │
                     └─────────────┘
```

---

## 二、核心组件

### 1. 检索器 (Retriever) - `make_retriever()`

**位置**: `src/agents/knowledge_base_agent/retrievers.py`

**作用**: 创建 Milvus 向量检索器，支持灵活的检索配置

**参数**:
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `collection_name` | str | - | Milvus 集合名称 |
| `k` | int | 5 | 返回的文档数量 |
| `expr` | str \| None | None | Milvus 过滤表达式 |

**返回**: Milvus 向量检索器实例

**示例代码**:
```python
retriever = make_retriever(
    collection_name="knowledge_base_doc",
    k=5,
    expr='metadata["dept_key"] in ["AI", "micro_service"]'
)
retrieved_docs = await retriever.ainvoke(query)
```

---

### 2. 检索节点 - `retrieve_documents()`

**位置**: `src/agents/knowledge_base_agent/nodes_doc.py`

**作用**: 根据用户查询检索相关文档，并应用权限过滤

**处理流程**:
```
1. 提取用户查询（最新一条 HumanMessage）
2. 获取用户权限（allowed_dept_keys）
3. 构建 Milvus 过滤表达式
4. 检索相关文档
5. 格式化文档元数据
6. 返回检索结果
```

**权限处理逻辑**:

| allowed_dept_keys | 过滤表达式 | 行为 |
|-------------------|------------|------|
| `[]` (空) | `'metadata["dept_key"] in ["__none__"]'` | 拒绝访问，返回提示信息 |
| `["*"]` | `None` | 允许访问所有部门 |
| `["AI", "micro_service"]` | `'metadata["dept_key"] in ["AI", "micro_service"]'` | 只允许指定部门 |

**无结果处理**:
- 未检索到文档时，返回友好的提示信息
- 明确告知可能存在权限限制

**返回的文档结构**:
```python
{
    "id": "doc-1",                    # chunk_id
    "source": "/path/to/file.pdf",    # 文件路径
    "title": "Document 1",            # 文档标题
    "content": "文档内容...",           # 文档内容
    "relevance_score": 0.85,          # 相关性得分
    "dept_key": "AI",                 # 部门标识
    "file_id": "550e8400-...",        # 文件UUID（用于生成链接）
    "filename": "白皮书.pdf",         # 文件名
    "page": 4,                        # 页码
}
```

---

### 3. 增强提示词节点 - `prepare_augmented_prompt()`

**位置**: `src/agents/knowledge_base_agent/nodes_doc.py`

**作用**: 将检索到的文档格式化为 LLM 可理解的上下文

**格式化示例**:
```
--- Document 1 ---
File: 产品白皮书.pdf
Page: 4
File ID: 550e8400-e29b-41d4-a716-446655440000
Title: 产品概述

产品提供了高吞吐性能...
```

---

### 4. 模型调用节点 - `acall_model()`

**位置**: `src/agents/knowledge_base_agent/nodes_doc.py`

**作用**: 使用检索到的文档作为上下文，调用 LLM 生成回答

**处理流程**:
1. 检查 `stop_chain` 标志，如果为 True 则直接返回
2. 获取配置的 LLM 模型
3. 包装系统提示词 + 文档上下文 + 历史对话
4. 调用 LLM 生成回答
5. 触发自动评估（如果有 trace_id）

---

## 三、Milvus 配置详解

### 3.1 连接配置

**连接参数构建** - `build_connection_args()`

| 参数 | 环境变量 | 类型 | 必填 | 说明 |
|------|----------|------|------|------|
| `uri` | `MILVUS_URI` | str | 是 | Milvus 服务地址，如 `http://localhost:19530` |
| `token` | `MILVUS_TOKEN` | str | 否 | Token 认证 |
| `user` | `MILVUS_USERNAME` | str | 否 | 用户名认证（与 password 一起使用） |
| `password` | `MILVUS_PASSWORD` | str | 否 | 密码认证（与 user 一起使用） |
| `db_name` | `MILVUS_DB_NAME` | str | 否 | 数据库名称 |
| `secure` | `MILVUS_TLS` | bool | 否 | 是否启用 TLS，默认 false |

**认证规则**:
- `token` 和 `user/password` 互斥，不能同时设置
- 如果设置了 `token`，使用 Token 认证
- 如果设置了 `user/password`，使用用户名密码认证
- 两者都未设置，使用无认证连接

### 3.2 集合 (Collection) 结构

**字段定义**:

| 字段名 | 类型 | 主键 | 说明 | 最大长度 |
|--------|------|------|------|----------|
| `id` | VARCHAR | ✅ | Chunk 唯一标识 | 128 |
| `vector` | FLOAT_VECTOR | ❌ | 向量嵌入 | 动态（取决于模型） |
| `text` | VARCHAR | ❌ | 文本内容 | 8192（可配置） |
| `metadata` | JSON | ❌ | 元数据 | - |

**Collection Schema**:
```python
fields = [
    FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, auto_id=False, max_length=128),
    FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=1024),  # dim 取决于 embedding 模型
    FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=8192),
    FieldSchema(name="metadata", dtype=DataType.JSON),
]
```

### 3.3 索引配置

**索引类型**: `IVF_FLAT`

| 参数 | 值 | 说明 |
|------|-----|------|
| `index_type` | `IVF_FLAT` | 倒排文件索引 |
| `metric_type` | `COSINE` | 余弦相似度 |
| `nlist` | 1024 | 聚类中心数量 |

**索引创建代码**:
```python
coll.create_index(
    field_name="vector",
    index_params={
        "index_type": "IVF_FLAT",
        "metric_type": "COSINE",
        "params": {"nlist": 1024},
    },
)
```

### 3.4 搜索参数配置

**Milvus 向量存储初始化参数**:

| 参数 | 值 | 环境变量 | 说明 |
|------|-----|----------|------|
| `primary_field` | `"id"` | - | 主键字段名 |
| `vector_field` | `"vector"` | - | 向量字段名 |
| `text_field` | `"text"` | - | 文本字段名 |
| `metadata_field` | `"metadata"` | - | 元数据字段名 |
| `auto_id` | `False` | - | 不自动生成 ID |
| `metric_type` | `"COSINE"` | - | 距离度量类型 |
| `nprobe` | 32 | `MILVUS_NPROBE` | 搜索时探测的聚类中心数量 |

**代码示例**:
```python
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
```

### 3.5 分块策略配置

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `chunk_size` | 2000 | 每个 chunk 的字符数 |
| `chunk_overlap` | 500 | 相邻 chunk 的重叠字符数 |

**代码**:
```python
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=2000,
    chunk_overlap=500
)
```

### 3.6 Metadata 结构

每个 chunk 包含的元数据:

| 字段 | 类型 | 说明 |
|------|------|------|
| `source` | str | 文件路径 |
| `filename` | str | 文件名 |
| `doc_id` | str | 文件内容 SHA1（唯一标识文件） |
| `page` | str/int | 页码 |
| `chunk_index` | int | chunk 在文档中的索引 |
| `chunk_id` | str | chunk 唯一 ID（格式: `{doc_id}:{page}:{idx}`） |
| `dept_key` | str | 部门标识 |
| `file_id` | str | 文件 UUID（用于前端生成文档链接） |

---

## 四、权限控制

### 4.1 权限表达式构建

**函数**: `_build_milvus_expr_for_dept_keys(allowed)`

**状态定义**:

| 状态 | allowed_dept_keys | 返回表达式 | 说明 |
|------|-------------------|------------|------|
| `DENY_ALL` | `[]` | `'metadata["dept_key"] in ["__none__"]'` | 无权限，保证无结果 |
| `ALLOW_ALL` | `["*"]` | `None` | 允许所有部门 |
| `ALLOW_SOME` | `["AI", "micro_service"]` | `'metadata["dept_key"] in ["AI", "micro_service"]'` | 只允许指定部门 |

### 4.2 权限检查流程

```
用户发起查询
    │
    ▼
获取 allowed_dept_keys (从 user_context)
    │
    ├─> 空列表 → DENY_ALL → 返回无权限提示
    │
    ├─> 包含 "*" → ALLOW_ALL → 无过滤
    │
    └─> 具体部门 → ALLOW_SOME → 构建 dept_key 过滤表达式
             │
             ▼
         Milvus 检索（带表达式过滤）
```

### 4.3 无权限/无结果处理

**DENY_ALL 响应**:
```
你当前没有访问对应企业知识库文档的权限，请联系管理员或在权限系统中申请相应部门的访问权限。
```

**ALLOW_SOME 但无结果响应**:
```
未检索到你当前可访问的相关文档。由于权限限制，可能存在相关资料但你暂无权限查看；
请申请相应部门的访问权限或联系管理员。
```

---

## 五、文档导入流程

### 5.1 支持的文件类型

| 类型 | 扩展名 | Loader |
|------|--------|--------|
| PDF | `.pdf` | `PyPDFLoader` |
| DOCX | `.docx` | `Docx2txtLoader` |

### 5.2 导入流程

```
1. 加载文档
   │
   ├─> PDF: PyPDFLoader
   └─> DOCX: Docx2txtLoader
   │
2. 文本分块
   │   ├─ chunk_size: 2000
   │   └─ chunk_overlap: 500
   │
3. 生成向量嵌入
   │   └─ 使用缓存的 Embedding 模型
   │
4. 生成 IDs
   │   ├─ doc_id = SHA1(file_content)
   │   ├─ file_id = UUID5(NAMESPACE_URL, "{dept_key}/{filename}")
   │   └─ chunk_id = "{doc_id}:{page}:{idx}"
   │
5. 构建 Metadata
   │   └─ source, filename, doc_id, page, chunk_index, chunk_id, dept_key, file_id
   │
6. 添加到 Milvus
   │
7. 完成
```

### 5.3 文档 ID 生成规则

**doc_id**: 文件内容的 SHA1 哈希值
- 用于唯一标识文件（避免同名冲突）
- 用于版本区分（同一文件内容变化会产生新 doc_id）
- 用于删除操作（根据 doc_id 删除所有相关 chunks）

**file_id**: 基于 namespace 的 UUID5
- 格式: `uuid5(NAMESPACE_URL, "{dept_key}/{filename}")`
- 用于前端生成可点击的文档链接
- 跨环境保持一致（相同 dept_key + filename 生成相同的 file_id）

**chunk_id**: chunk 唯一标识
- 格式: `"{doc_id}:{page}:{idx}"`
- 用于 Milvus 的主键

---

## 六、嵌入模型管理

### 6.1 模型配置

| 参数 | 环境变量 | 默认值 | 说明 |
|------|----------|--------|------|
| 模型名称 | `EMBEDDING_MODEL_NAME` | `BAAI/bge-m3` | HuggingFace 模型名称 |
| 运行设备 | `EMBEDDING_DEVICE` | `cpu` | cpu/cuda/mps 等 |
| 归一化 | `NORMALIZE_EMBEDDINGS` | `true` | 是否对向量进行归一化 |

### 6.2 模型缓存机制

**位置**: `src/core/embeddings.py`

**特性**:
- 全局单例缓存（避免重复加载）
- 线程安全（使用 threading.Lock）
- 配置变更自动重新加载

**缓存 Key 格式**:
```
{model_name}:{device}:{normalize_embeddings}
```

**HuggingFace 本地缓存**:

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `HF_HOME` | `.hf_cache` | HuggingFace 根目录 |
| `HUGGINGFACE_HUB_CACHE` | `{HF_HOME}/hub` | Hub 缓存目录 |
| `TRANSFORMERS_CACHE` | `{HF_HOME}/transformers` | Transformers 缓存目录 |

**强制使用本地缓存**:
- 避免联网下载模型
- 提升加载速度
- 确保离线环境可用

---

## 七、评估机制

### 7.1 评估器类型

| 评估器 | 文件 | 说明 |
|--------|------|------|
| `CitationEvaluator` | `citation_evaluator.py` | 评估回答中是否包含引用 |
| `CitationCorrectnessEvaluator` | `citation_correctness_evaluator.py` | 评估引用的正确性 |
| `NeedsClarificationEvaluator` | `needs_clarification_evaluator.py` | 评估是否需要澄清问题 |
| `SafetyRiskEvaluator` | `safety_risk_evaluator.py` | 评估回答的安全性风险 |

### 7.2 自动评估流程

**位置**: `src/agents/knowledge_base_agent/nodes_doc.py`

**触发时机**: LLM 调用完成后

**代码**:
```python
if hasattr(response, "id"):
    evaluation_manager.evaluate_all(
        output=str(response.content) if response.content else "",
        context={
            "trace_id": str(response.id),
            "input": state.get("messages", [])[-1].content if state.get("messages") else None,
        },
    )
```

**评估管理器**:
```python
evaluation_manager = EvaluationManager()
evaluation_manager.register(CitationEvaluator())
evaluation_manager.register(NeedsClarificationEvaluator())
evaluation_manager.register(SafetyRiskEvaluator())
evaluation_manager.register(CitationCorrectnessEvaluator())
```

---

## 八、完整流程图

```
┌─────────────────────────────────────────────────────────────────┐
│              RAG 检索完整流程                                      │
└─────────────────────────────────────────────────────────────────┘

用户输入查询
    │
    ▼
┌──────────────────────────────────────────────────────┐
│  retrieve_documents() 检索节点                         │
├──────────────────────────────────────────────────────┤
│  1. 提取用户查询                                       │
│  2. 获取 allowed_dept_keys (从 config)                │
│  3. 构建权限过滤表达式                                 │
│     ├─ DENY_ALL: 返回无权限提示                       │
│     ├─ ALLOW_ALL: 无过滤                              │
│     └─ ALLOW_SOME: dept_key 过滤                      │
│  4. 调用 Milvus 检索                                  │
│     └─ make_retriever(collection_name, expr)         │
│  5. 无结果 → 返回友好提示                              │
│  6. 格式化文档元数据                                   │
└──────────────────────────────────────────────────────┘
    │
    │ retrieved_documents: list[dict]
    ▼
┌──────────────────────────────────────────────────────┐
│  prepare_augmented_prompt() 增强提示词节点            │
├──────────────────────────────────────────────────────┤
│  1. 将文档格式化为 Markdown 格式                       │
│     ├─ File: xxx                                      │
│     ├─ Page: xxx                                       │
│     ├─ File ID: xxx                                   │
│     └─ Title: xxx + content                          │
│  2. 拼接所有文档                                      │
│  3. 保存到 kb_documents 字段                          │
└──────────────────────────────────────────────────────┘
    │
    │ kb_documents: str
    ▼
┌──────────────────────────────────────────────────────┐
│  acall_model() 模型调用节点                           │
├──────────────────────────────────────────────────────┤
│  1. 检查 stop_chain 标志                              │
│  2. 获取 LLM 模型                                     │
│  3. wrap_model() 包装系统提示词                       │
│     ├─ SystemMessage: DOC_SYSTEM_PROMPT              │
│     ├─ HumanMessage: 文档上下文 (kb_documents)       │
│     └─ 历史对话消息                                   │
│  4. 调用 LLM 生成回答                                 │
│  5. 触发自动评估 (如果有 trace_id)                     │
└──────────────────────────────────────────────────────┘
    │
    │ AIMessage (包含引用链接)
    ▼
返回用户
```

---

## 九、系统提示词

**位置**: `src/agents/knowledge_base_agent/prompts.py`

**DOC_SYSTEM_PROMPT**:
```
你是一个乐于助人的助手，会基于检索到的文档提供准确的信息。

你将收到一个查询，以及从知识库中检索到的相关文档。请使用这些文档来支撑你的回答。

请遵循以下准则：
1. 你的回答应主要基于检索到的文档
2. 如果文档中包含答案，请清晰、简洁地给出
3. 如果文档信息不足，请向用户解释'根据现有权限所能获取到的文档信息，我无法找找到足够的信息来回答你的问题'
4. 绝不编造文档中不存在的事实或信息
5. 当引用具体信息时，务必标注来源文档，并生成可点击的文档链接
6. 如果文档之间存在矛盾，请承认并解释不同的观点

**文档引用格式要求：**
- 每个文档都有 File ID，请使用该 ID 生成可点击的 Markdown 链接
- 链接格式：`[文档名称 - 第X页](/kb/files/{file_id}/download)`
- 示例：根据产品文档 [CKafka产品白皮书 - 第4页](/kb/files/550e8400-e29b-41d4-a716-446655440000/download) 所述，CKafka提供高吞吐性能...
- 如果同一文档被多次引用，首次引用时显示完整链接，后续可以简化为 [同上文] 或 [文档X]
- 在回答的关键信息处插入文档引用，让用户可以直接点击链接查看原文

**注意：**
- File ID 会包含在每个文档的信息中（格式为 "File ID: xxx"）
- 文档名称和页码也会提供（格式为 "File: xxx" 和 "Page: xxx"）
- 请根据这些信息生成准确的文档链接

请以清晰、自然的对话方式组织回答；在合适的情况下使用 Markdown 格式。
```

---

## 十、环境变量配置

### 10.1 Milvus 连接配置

| 变量 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `MILVUS_URI` | 是 | - | Milvus 服务地址 |
| `MILVUS_TOKEN` | 否* | - | Token 认证 |
| `MILVUS_USERNAME` | 否* | - | 用户名认证 |
| `MILVUS_PASSWORD` | 否* | - | 密码认证 |
| `MILVUS_DB_NAME` | 否 | - | 数据库名称 |
| `MILVUS_TLS` | 否 | `false` | 是否启用 TLS |

*注：`MILVUS_TOKEN` 和 `MILVUS_USERNAME`/`MILVUS_PASSWORD` 互斥

### 10.2 Milvus 检索配置

| 变量 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `MILVUS_COLLECTION_DOC` | 否 | `knowledge_base_doc` | 文档集合名称 |
| `MILVUS_NPROBE` | 否 | `32` | 搜索时探测的聚类中心数量 |

### 10.3 嵌入模型配置

| 变量 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `EMBEDDING_MODEL_NAME` | 否 | `BAAI/bge-m3` | HuggingFace 模型名称 |
| `EMBEDDING_DEVICE` | 否 | `cpu` | 运行设备（cpu/cuda/mps） |
| `NORMALIZE_EMBEDDINGS` | 否 | `true` | 是否对向量进行归一化 |

### 10.4 HuggingFace 缓存配置

| 变量 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `HF_HOME` | 否 | `.hf_cache` | HuggingFace 根目录 |

### 10.5 示例配置文件

```bash
# .env

# Milvus 连接
MILVUS_URI=http://localhost:19530
MILVUS_TOKEN=
MILVUS_USERNAME=
MILVUS_PASSWORD=
MILVUS_DB_NAME=
MILVUS_TLS=false

# Milvus 检索
MILVUS_COLLECTION_DOC=knowledge_base_doc
MILVUS_NPROBE=32

# 嵌入模型
EMBEDDING_MODEL_NAME=BAAI/bge-m3
EMBEDDING_DEVICE=cpu
NORMALIZE_EMBEDDINGS=true

# HuggingFace 缓存
HF_HOME=.hf_cache
```

---

## 附录：相关代码位置

| 模块 | 文件路径 |
|------|----------|
| 检索节点 | `src/agents/knowledge_base_agent/nodes_doc.py` |
| 检索器 | `src/agents/knowledge_base_agent/retrievers.py` |
| 系统提示词 | `src/agents/knowledge_base_agent/prompts.py` |
| Agent 状态 | `src/agents/knowledge_base_agent/state.py` |
| Milvus 服务 | `src/service/milvus_service.py` |
| 嵌入模型管理 | `src/core/embeddings.py` |
| 评估器 | `src/evaluation/` |

---

## 更新日志

- 2026-01-23: 初始版本，记录 RAG 检索系统架构和 Milvus 配置详解
