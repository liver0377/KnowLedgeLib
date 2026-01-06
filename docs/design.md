# 1. 产品概述

## 1.1 产品定义

KnowledgeLib 是一款**面向企业内部使用的、具备权限控制能力的智能知识助手**。系统通过 **检索增强生成（Retrieval-Augmented Generation, RAG）** 与 **工具调用 Agent（Tool-Calling Agent）**， 为企业员工提供对**内部文档与结构化数据的统一、可靠、可追溯且受权限约束**的自然语言访问能力。

该系统并非通用聊天机器人，而是定位为企业内部的**知识与数据访问层（Knowledge & Data Access Layer）**

- 所有回答均基于真实的企业内部数据

- 数据访问严格遵循企业既有的权限与组织边界

- 回答具备明确来源，可审计、可追溯

- 支持多步问题的自动分析与处理



## 1.2 产品愿景

本产品的愿景是让企业员工能够像与一名 **“既熟悉公司内部知识，又清楚自己权限边界的同事”**进行对话一样，通过自然语言**安全、高效地获取准确信息并完成基础业务查询任务**。系统不仅关注“能否回答问题”， 更关注在企业环境中：

- 回答是否**安全**

- 是否**越权**

- 是否**可追溯、可审计**

- 是否符合企业合规与治理要求



## 1.3 目标用户

- 本产品主要面向 **中小型及中型企业的内部员工**，典型用户包括：

  - **技术工程师**
     查询技术文档、部署规范、系统配置说明，在其所属项目或部门权限范围内获取信息。
  - **产品或运营人员**
     通过自然语言查询业务规则、指标定义或结构化数据，无需直接接触底层数据库。
  - **部门或项目管理员（间接用户）**
     通过文件夹级权限配置与审计能力，对企业知识资产进行集中管理与治理。

  本项目暂不考虑以下场景：

  - 面向公众的 C 端用户
  - 高并发的大规模在线服务
  - 跨企业、多租户的 SaaS 化平台



## 1.4 用户痛点

- 企业文档分散，检索效率低
- 纯大模型问答存在幻觉风险
- 结构化数据访问门槛高
- 权限配置与治理成本高
- 复杂问题需要多步人工处理



## 1.5 产品核心价值

- 基于RAG的可靠能力问答

  所有的回答均基于企业内部文档进行生成，并支持引用原始内容，有效降低大模型幻觉风险

- Agent驱动的自动化工具调用

- 统一的知识与数据访问入口

- 具备拓展性的工程化架构

- **具备治理与扩展能力的工程化架构**
   系统支持权限继承、审计日志、数据导出等企业级能力，并可在后续阶段扩展至更多数据源与管理场景。







# 2. 用户场景

## 场景一：基于企业文档的精准问答（RAG核心场景)

用户角色: 后端/运维工程师

问题类型: 非结构化文档检索

**典型问题**：

- “Kubernetes 中 Deployment 的 rolling update 默认策略是什么？”
- “在内部部署规范中，服务超时时间如何配置？”
- “某个组件的推荐资源限制是多少？”

**现有痛点**：

- 文档内容分散在多个 PDF / Wiki 页面中
- 关键词搜索命中不准，需要人工翻页查找
- 纯 LLM 容易给出与文档不一致的答案

**系统行为**：

1. Agent 判断问题需要文档检索
2. 调用 RAG 检索工具，从技术文档中召回相关段落
3. 基于检索内容生成答案，并附带引用来源



## 场景二：结构化数据的自然语言查询（Tool Calling 场景)

**用户角色**：产品经理 / 运营人员
**问题类型**：结构化数据查询
**典型问题**：

- “目前 A 类产品一共有多少个？”
- “上个月新增了多少用户？”
- “当前在进行中的项目有哪些？”

**现有痛点**：

- 用户不会写 SQL
- 简单数据问题需要反复找技术人员协助
- 查询流程割裂、效率低

**系统行为**：

1. Agent 判断问题涉及结构化数据
2. 将自然语言转换为 SQL 查询
3. 调用 SQL 工具执行查询
4. 对结果进行总结并返回自然语言答案



## 场景三：多步问题的自动处理（Agent 核心能力）

**用户角色**：项目负责人
**问题类型**：复合型、多步骤问题
**典型问题**：

- “根据部署文档的说明，目前支持哪些环境？这些环境中有多少正在使用？”
- “结合员工手册和人员表，新员工的试用期是多久？目前有多少人在试用期？”

**现有痛点**：

- 需要先查文档，再查数据
- 多系统切换，人工整合信息
- 易出错、耗时长

**系统行为**：

1. Agent 拆解问题为多个子任务
2. 分别调用：
   - 文档检索工具（RAG）
   - 结构化查询工具（SQL）
3. 汇总多个工具返回的结果
4. 生成最终综合回答





# 3. 功能需求

## 3.1 核心功能

### 3.1.1 文档接入与管理

- 系统应支持上传企业内部文档作为知识源
- 支持的文档格式: PDF, Markdown, docx, excel
- 系统应该对文档进行解析，切分并且建立索引



### 3.2.2 基于RAG的文档问答

- 系统应该基于企业文档内容进行问答
- 回答应由检索到的文档内容支撑
- 系统应该在回答中提供文档引用信息



### 3.2.3 Tool-Calling Agent

- 系统应引入Agent机制，对用户问题进行分析
- Agent应该能够根据问题类型选择合适的工具
- 至少支持以下工具:
  - 文档检索工具(RAG Retriever)
  - 结构化数据查询工具(SQL Tool)



### 3.2.4 多轮对话支持

- 系统应支持基本的多轮对话能力
- 系统应在当前会话中保留必要的上下文信息
- 上下文长度应受到合理兼职，避免无关信息干扰



## 3.2 支持功能

### 3.2.1 基础评估与可观测性

- 系统应记录每次请求的基本信息，包括：
  - 用户问题
  - 检索结果
  - 响应耗时
- 支持对检索效果和回答质量进行基础评估



## 3.3 拓展功能

### 3.3.1 内部网页型知识源接入

- 系统拓展支持内部Wiki或网页内容的接入
- 通过网页采集与定期索引方式更新知识库



### 3.3.2 权限与访问控制

- 支持基于用户角色的知识访问控制
- 不同用户可以访问不同范围的企业知识



# 4. 系统设计

本系统采用**Single Agent + Workflow-Orchestrated ReAct**的设计:

- **Single Agent**: 唯一决策主体，负责理解问题，选择工具，汇总答案
- **Workflow(状态机)**: 显示控制执行路径、重试预算、停止条件与降级策略，保证可控，可复现，可调试
- **ReAct-style tool use**: 在"工具调用节点"内部, Agent以"决策 → 调用 → 观察"的循环获取证据, 但循环被workflow的step limit, no-new-info等规则限制



## 4.1 总体架构

系统由四个子系统组成:

1. 文档接入与索引
   - 上传/导入文档(pdf/markdown/txt/docx)
   - 文本解析 → chunk切分 → embedding → 向量索引(FAISS) → 元数据存储(SQLite/JSON)
2. 检索层
   - dense retrieval top-k（使用Cross-Encoder rerank)
   - 输出chunks与可引用元信息(doc/page/chunk_id)
3. Workflow & Agent
   - Route: 将问题路由到DOC/SQL/CALC/HYBRID
   - Tool Nodes: 调用RAG/SQL/Calculation等工具
   - Validate: 证据校验与停止判定
   - Synthesize: 基于证据生成最终答案（强制引用或abstain)
4. 服务与可观测性
   - 接口: upload, chat
   - 日志: tool trace, retrieval 命中, 延迟，错误， stop_reason
   - 评估: 离线问题集 + 指标(Recal@k, Correctness)



## 4.2 State Schema

- append-only

  - messages: list[BaseMessage]

  - trace_steps: list[dict]

    ```json
    {
      // 每一步 trace 的唯一标识（递增或 UUID 都行）
      "step_id": "step_0001",
    
      // 发生时间（毫秒时间戳）
      "ts_ms": 1735267200123,
    
      // 节点名：Preprocess / Route / DocRAGTool / SQLTool / Validate / Synthesize ...
      "node": "DocRAGTool",
    
      // 节点内部动作名：方便同一节点区分不同动作
      "action": "retrieve_and_pack",
    
      // 执行状态
      "status": "ok", // "ok" | "error" | "skipped"
    
      // 节点耗时（ms）
      "timing_ms": 186,
    
      // 本步的核心输入摘要（不要塞大文本，避免日志爆炸/泄露）
      "in": {
        "q": "k8s rolling update default strategy", // 归一化后的 query（可截断）
        "route": "DOC",                             // 可选：当时的 route
        "user": "u_123"                             // 可选：用户 id（或哈希）
      },
    
      // 本步的核心输出摘要
      "out": {
        "evidence_added": 3,                        // 新增了多少条 evidence
        "note": "retrieved=8 packed=3"              // 一句话总结（可选）
      },
    
      // 如果是 Tool Node，记录工具名；非 Tool Node 可省略
      "tool": "rag_retriever", // 例如 "rag_retriever" | "sql_tool"
    
      // 如发生错误，填简要错误；没有错误可省略
      "err": {
        "type": "ValidationError",
        "msg": "tenant/org filter is required"
      }
    }
    
    ```

    

  - evidence_items: list[dict]

    ```json
    {
      // 证据唯一标识：建议可复现（source + id + hash）
      "evidence_id": "doc:deploy_spec_v3:chunk_001:a1b2c3d4",
    
      // 证据类型：文档片段 or SQL结果
      "type": "doc_chunk", // "doc_chunk" | "sql_result"
    
      // 证据正文：尽量是“可引用的最小片段”
      // 注意：不要太长；可在入库时截断，比如 500~1200 chars
      "text": "Deployment rolling update 默认策略为 ...",  // 对于SQL, 存储结果摘要 + top rows
    
      // 用于排序/置信度的分数（doc检索用；SQL可为 null 或 1.0）
      "score": 0.78,
    
      // 证据来源信息：用于 UI 展示与追溯
      "source": {
        // 文档场景
        "doc_id": "deploy_spec_v3",         // 内部文档ID（或路径）
        "title": "Internal Deployment Spec",
        "page": 3,                          // PDF 页码（可选）
        "chunk_id": "chunk_001",            // chunk id（可选）
        "uri": "kb://team-a/deploy/spec"    // 内部链接（可选）
    
        // SQL 场景（如果 type=sql_result，可改成）
        // "db": "analytics",
        // "table": "users",
        // "query_id": "q_20251227_0009"
      },
    
      // 权限检查结果：最小审计字段
      "authz": {
        "result": "allow",                  // "allow" | "deny" | "filtered"
        "perm_snapshot_id": "perm_20251227_001"
      },
    
      // 证据生成方式：便于审计（RAG/SQL/用户提供）
      "by": "retriever", // "retriever" | "sql" | "user"
    
      // 可选：用于防篡改/去重（hash of text + source ids）
      "hash": "a1b2c3d4"
    }
    
    ```

    在回答中，只引用evidence_id, UI通过`evidence_id`找到`evidence_item`

  

- 覆盖

  - input: dict

    ```json
    {
      // 原始用户问题（必填）
      "query": "Kubernetes 中 Deployment 的 rolling update 默认策略是什么？",
    
      // 预处理后的 query（PreprocessNode 写入）
      "normalized_query": "kubernetes deployment rolling update 默认策略是什么",
    
      // 可选：当前会话的一些轻量上下文（先别复杂化）
      "session_id": "sess_001",
      "user_id": "admin"
    
      // 可选：用户上传的附件/文档引用（v0 可先留空）
      "attachments": [
        // {"type":"file","file_id":"f_123","name":"spec.pdf"}
      ]
    }
    
    ```

    

  - authz: dict

    ```json
    {
      // 鉴权信息
      // 用户身份（必填）
      "user_id": "u_123",
       
       // 租户id
       "tenant_id": str,
    
      // 用户角色（RBAC）
      "roles": ["engineer"],
    
      // 用户组织/项目范围（用于过滤可访问知识）
      "org_units": ["team-a", "project-x"],
    
      // 权限快照ID：用于审计复现（建议必填）
      "perm_snapshot_id": "perm_20251227_001"
    }
    
    ```

  - plan: dict

    ```json
    {
      // 路由结果：RouteNode 写入
      "route": "DOC", // "DOC" | "SQL" | "CLARIFY"
    
      // 一句话意图（可选，但很有用）
      "intent": "ask_policy_from_docs",
    
      // 当 route=CLARIFY 时给出澄清问题（v0 用一个问题就行）
      "clarifying_questions": [
        // "你是想查询内部文档内容，还是想统计数据库里的业务数据？"
      ],
    
      // v0 简化：不做 subtasks；后续要做 HYBRID 再加
      "validation": {
        // ValidateEvidenceNode 写入
        "ok": true,
        "reason": null // "no_evidence" | "permission_denied" | null
      }
    }
    
    ```

    

  - tools: dict

    ```json
    {
      // DOC RAG 工具的摘要（DocRAGToolNode 写入）
      "rag": {
        "query": "kubernetes deployment rolling update 默认策略是什么",
        "top_k": 8,
    
        // 可选：权限/目录过滤摘要（具体规则别全塞进来，避免泄露）
        "filters": {
          "scope": ["team-a", "project-x"]
        },
    
        // 本次 RAG 生成的 evidence_id 列表（用于定位）
        "returned_evidence_ids": [
          "doc:deploy_spec_v3:chunk_001:a1b2c3d4",
          "doc:k8s_handbook:chunk_114:9f8e7d6c"
        ]
      },
    
      // SQL 工具摘要（SQLToolNode 写入；v0 合并版）
      "sql": {
        // 生成的 SQL（注意脱敏/避免写入敏感常量）
        "generated_sql": "SELECT COUNT(*) AS cnt FROM users WHERE tenant_id=? AND created_at>=? AND created_at<? LIMIT 50",
    
        // 结果预览（v0 建议只放 1~2 行摘要）
        "result_preview": "cnt=128",
    
        // SQL 产生的 evidence_id（如果有）
        "returned_evidence_ids": [
          "sql:q_20251227_0009:rowset:3c2b1a00"
        ]
      },
    
      // 可选：工具错误列表（v0 先留一个数组即可）
      "errors": [
        // {"tool":"sql_tool","type":"ValidationError","msg":"tenant/org filter is required"}
      ]
    }
    
    ```

    

  - draft: dict

    ```json
    {
      // 生成的答案草稿
      "answer": "根据内部部署规范，Deployment 的 rolling update 默认策略是 ...",
    
      // 引用：最简版只存 evidence_id；后面再加 span(start/end)
      "citations": [
        { "evidence_id": "doc:deploy_spec_v3:chunk_001:a1b2c3d4" },
        { "evidence_id": "doc:k8s_handbook:chunk_114:9f8e7d6c" }
      ],
    
      // 一个粗略置信度（0~1），v0 可先写死规则：有证据=0.7+
      "confidence": 0.78,
    
      // 可选：后续追问建议（v0 可先不做）
      "followups": [
        // "你想查看对应的配置示例吗？"
      ]
    }
    
    ```

    

  - output: dict

    ```json
    {
      // 最终答案文本（通常等于 draft.answer）
      "final_answer": "根据内部部署规范，Deployment 的 rolling update 默认策略是 ...",
    
      // 最终引用（通常等于 draft.citations）
      "final_citations": [
        { "evidence_id": "doc:deploy_spec_v3:chunk_001:a1b2c3d4" },
        { "evidence_id": "doc:k8s_handbook:chunk_114:9f8e7d6c" }
      ],
    
      // 可选：为了前端渲染，把 evidence 的核心展示信息提前整理（避免前端再查）
      "rendered_sources": [
        {
          "evidence_id": "doc:deploy_spec_v3:chunk_001:a1b2c3d4",
          "title": "Internal Deployment Spec",
          "page": 3,
          "uri": "kb://team-a/deploy/spec"
        }
      ],
    
      // 可选：停止原因/结果状态（v0 简单几个枚举就够）
      "stop_reason": "ok" // "ok" | "need_clarify" | "no_evidence" | "permission_denied" | "tool_error"
    }
    
    ```

    



## 4.3 Node定义

### 4.3.1 PreprocessNode

**职责**：清洗用户 query，做轻量标准化（去多余空格/控制字符），可选语言检测

读取:

- `state["input"]["query"]`

写入(覆盖):

- `state[input]['normalized_query']`

写入(追加):

- `trace_steps += {node, action, timing_ms, status, ...}`



### 4.3.2 LoadAuthzNode

**职责**：加载权限上下文快照（先做“模拟/固定数据”也行），后续所有工具调用都带上它

读取

- `state["input"]["user_id"]`

写入(覆盖)

- `authz: {user_id, roles, org_units, perm_snapshot_id}`

写入(追加)

- `trace_steps += {node, action, timing_ms, status, ...}`



### 4.3.3 RouteNode

职责: 决定走DOC/SQL/CLARIFY

- 出现"多少/统计/新增/上月/列表/排名/指标" => SQL
- 出现"文档/规范/如何配置/默认策略/是什么" => DOC
- 意图不明确 => ClARIFY
- 请求越权，敏感数据，不在系统能力范围 => REFUSE

使用基于LLM的意图识别来进行路由

读取

- `state["input"]["normalized_query"]`
- `authz`



写入(覆盖)

- `state["plan"]["route"]`
- `state["plan"]["intent"]`
- `state["plan"]["clarifying_questions"]`



写入(追加)

- trace_steps



### 4.3.4 ToolNode: DocToolNode

职责: 检索 → 返回evidence, 把 evidence写入 evidence_items

读取

- `state["input"]["normalized_query"]`
- `authz`



写入 (覆盖)

- `state["tools"]["rag"]: {query, top_k, filters, returned_evidence_ids}`



写入 (追加)

- `evidence_items += [EvidenceItem...]`
- `tracesteps += ...`



### 4.3.5 ToolNode: SQLToolNode

职责: NL → SQL (简单模板/LLM) → 执行 → 把结果写成evidence_items

**读取**

- `input.normalized_query`
- `authz`



写入(覆盖)

- `tools.sql: {generated_sql, result_preview, returned_evidence_ids}`



写入(追加)

- `evidence_items += [...]`



SQL约束

- 强制只读: 禁止`insert/update/delete/drop/alter`
- 强制`LIMIT 50`
- 强制带`tenant/org filter`检查



### 4.3.6 ClarifyNode

职责: 输出澄清问题

读取

- `state["plan"]["clarifying_questions"]`



写入(覆盖)

- `state["output"]["final_answer"]`



写入(追加)

- `trace_steps +=`



### 4.3.7 ValidateEvidenceNode

职责: 只做“够不够 + 能不能用”，保持简单

- evidence 是否为空

- 是否全是 deny/filtered



读取

- `state["evidence_items"]`
- `state["plan"]["route"]`



写入(覆盖)

- `state["plan"]["validation"]`



写入(追加)

- `trace_steps += ...`



### 4.3.8 SynthesizeNode

职责: 根据evidence生成答案， 并产出citations(引用evidence_id)

强制要求； 不允许无引用的断言; 证据不足就说明无法从已授权资料确认



**读取**

- `input.normalized_query`
- `plan.route`
- `evidence_items`
- （可选）`messages`（最近 N 轮）

**写入（覆盖）**

- `draft: {answer, citations:[{evidence_id}], confidence}`
- `output.final_answer`
- `output.final_citations`

**写入（追加）**

- `trace_steps += ...`





## 4.4 Node图



# 5. 技术栈

- 前端: Vue3 + Vite
- UI组件库: Naive UI
- HTTP: fetch
- 后端: FastAPI + LangGraph
- 跨域: FastAPI CORS middleware





