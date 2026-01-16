# 🧰 KnowLedgeLib - AI知识库管理系统

一个基于 LangGraph、FastAPI 和 Vue.js 的 AI 知识库管理系统，集成权限控制、文档管理、智能问答等功能。

## 📋 功能特性

- **智能问答**: 基于 LangGraph 的多 Agent 系统，支持复杂的知识查询和推理
- **文档管理**: 支持 PDF 文档的上传、下载、删除和分类管理
- **权限控制**: 基于 RBAC 的细粒度权限管理，支持部门和角色级别的访问控制
- **向量检索**: 使用 Milvus 向量数据库实现高效的文档检索
- **实时流式响应**: 支持 SSE 流式输出，提供流畅的用户体验
- **多模态支持**: 支持文本和语音输入输出
- **权限审批**: 文档上传需要审批流程

## 🏗️ 系统架构

```
┌─────────────┐      ┌──────────────┐      ┌─────────────┐
│   Vue.js    │─────▶│   FastAPI    │─────▶│  Milvus    │
│   Frontend   │      │   Backend    │      │  Vector DB  │
└─────────────┘      └──────┬───────┘      └─────────────┘
                          │
                          │
                    ┌───────▼───────┐
                    │     MySQL     │
                    │   Database    │
                    └───────────────┘
```

## 📦 环境要求

- Python 3.10+
- Node.js 18+
- Mysql 8.0+
- Docker & Docker Compose
- Milvus 2.3+

## 🚀 快速开始

### 1. 安装项目依赖

#### 后端依赖安装

```bash
# 使用 uv 安装（推荐）
# 安装 uv
curl -LsSf https://astral.sh/uv/0.7.19/install.sh | sh

# 安装依赖
uv sync --frozen
source .venv/bin/activate
```

或使用 pip：

```bash
# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate

# 安装依赖
pip install -r pyproject.toml
```

#### 前端依赖安装

```bash
cd frontend
npm install
```

### 2. 配置环境变量

复制 `.env.example` 并修改：

```bash
cp .env.example .env
```

配置必要的环境变量：

```env
# LLM 配置
OPENAI_API_KEY=your_openai_api_key
# 或使用其他 LLM 提供商

# 数据库配置（Docker）
# 使用 Docker Compose 启动时，数据库连接由 infra 目录下的配置管理
# PostgreSQL（推荐用于生产环境）
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=liver0377
POSTGRES_PASSWORD=sq17273747
POSTGRES_DB=knowledgelib

# MySQL（权限管理用）
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=rootpass
MYSQL_DATABASE=knowledge_lib

# Milvus 配置
MILVUS_HOST=localhost
MILVUS_PORT=19530

# JWT 密钥（必须）
JWT_SECRET_KEY=your_secret_key_here

# Langfuse 追踪（可选）
LANGFUSE_TRACING=true
LANGFUSE_PUBLIC_KEY=your_langfuse_public_key
LANGFUSE_SECRET_KEY=your_langfuse_secret_key
LANGFUSE_HOST=https://cloud.langfuse.com
# 启用自动评估（如引用存在性检测）
LANGFUSE_AUTO_EVAL=true
```

### 3. 启动数据库服务（Docker）

项目在 `infra` 目录下分别配置了各个数据库服务，包括 MySQL、PostgreSQL 和 Milvus。

#### 启动 Milvus（向量数据库）

```bash
cd infra/milvus
docker compose up -d
```

Milvus 服务包括：
- **etcd**: 元数据存储
- **minio**: 对象存储（用于 Milvus）
- **standalone**: Milvus 核心服务

服务访问地址：
- **Milvus API**: `localhost:19530`
- **MinIO Console**: `http://localhost:9001`
- **健康检查**: `http://localhost:19530/healthz`

#### 启动 PostgreSQL（推荐用于生产环境）

```bash
cd infra/postgres
docker compose up -d
```

服务访问地址：
- **PostgreSQL**: `localhost:5432`
  - 用户名: `liver0377`
  - 密码: `sq17273747`
  - 数据库: `knowledgelib`

#### 启动 MySQL

```bash
cd infra/mysql
docker compose up -d
```

服务访问地址：
- **MySQL**: `localhost:3306`
  - 用户名: `root`
  - 密码: `rootpass`
  - 数据库: `knowledge_lib`

### 4. 验证数据库服务

#### 验证 Milvus 运行状态

```bash
# 检查 Milvus 状态
curl http://localhost:19530/healthz

# 应返回：{"status":"ok"}
```

#### 验证 PostgreSQL 连接

```bash
# 连接测试
docker exec -it langgraph-pg psql -U liver0377 -d knowledgelib
```

#### 验证 MySQL 连接

```bash
# 连接测试
docker exec -it knowledge-mysql mysql -u root -prootpass
```

### 5. 准备向量数据库数据（Text2SQL）

在创建 Milvus 集合之前，需要确保 `data/` 目录下有以下文件：

#### 必需文件

- **`data/db_descriptions.json`**: 数据库表的描述信息
- **`data/ddl_examples.json`**: 数据库表的 DDL 示例
- **`data/qsql_examples.json`**: SQL 查询的示例

#### 可选文件

- **`data/AI/`**: AI 相关文档（PDF格式）
- **`data/database/`**: 数据库文档（PDF格式）
- **`data/micro_service/`**: 微服务文档（PDF格式）

这些文件会被 `scripts/create_milvus_db.py` 读取并导入到 Milvus 向量数据库。



### 6. 初始化数据库表结构

#### 初始化 MySQL 数据库（权限管理用）

```bash
# 确保已激活虚拟环境
source .venv/bin/activate

# 使用 docker-compose 在 MySQL 容器中执行 SQL 脚本
cd infra/mysql
docker compose exec -T mysql mysql -uroot -prootpass knowledge_lib < ../../scripts/rbac_schema.sql

# 导入 RBAC 初始数据
docker compose exec -T mysql mysql -uroot -prootpass knowledge_lib < ../../scripts/rbac_seed_data.sql

# 导入 Text2SQL 相关表
docker compose exec -T mysql mysql -uroot -prootpass knowledge_lib < ../../scripts/text2sql_schema.sql

# 导入 Text2SQL 初始数据
docker compose exec -T mysql mysql -uroot -prootpass knowledge_lib < ../../scripts/text2sql_seed_data.sql
```

该脚本会：
- 连接到 Docker 容器中的 MySQL 数据库
- 创建 RBAC 权限表结构（users, roles, departments, user_departments 等）
- 导入 Text2SQL 相关表结构
- 导入初始数据（默认角色、示例数据等）



### 8. 创建 Milvus 集合

```bash
# 确保已激活虚拟环境
source .venv/bin/activate

# 创建文档检索集合
python scripts/create_milvus_db.py
```

该脚本会：
1. 读取 `data/` 目录下的 JSON 文件（`db_descriptions.json`、`ddl_examples.json`、`qsql_examples.json`）
2. 连接到 Milvus 服务（`localhost:19530`）
3. 创建两个集合：
   - `knowledge_base_doc`: 文档检索集合
   - `knowledge_base_sql`: SQL 查询集合
4. 配置索引和参数（embedding 维度、距离度量等）



### 9. 导入文档到向量数据库

#### 使用脚本导入

```bash
# 确保已激活虚拟环境
source .venv/bin/activate

# 导入文档到 Milvus
python scripts/insert.py
```

该脚本会：
1. 读取 `data/AI/`、`data/database/`、`data/micro_service/` 目录下的所有 PDF 文档
2. 使用 PDF 解析器提取文本内容
3. 分割文本为 chunks
4. 生成 embedding 向量
5. 存储到 Milvus 文档集合（`knowledge_base_doc`）

#### 手动添加文档

通过前端界面上传：
1. 访问 http://localhost:8501
2. 登录系统
3. 进入"文件管理"页面
4. 点击"上传文件"
5. 选择 PDF 文件并上传

上传的文件会被：
1. 解析文本内容
2. 分割为 chunks
3. 生成 embedding 向量
4. 存储到 Milvus 向量数据库
5. 按部门分类存储

### 8. 启动应用服务

#### 使用 Docker Compose 启动（推荐）

```bash
# 启动所有服务（PostgreSQL + 后端 + 前端）
docker compose up

# 或使用 watch 模式（开发时自动更新）
docker compose watch
```

服务访问地址：
- 前端界面: http://localhost:8501
- 后端 API: http://localhost:8080
- API 文档: http://localhost:8080/redoc

#### 手动启动服务

**启动后端服务**：

```bash
# 激活虚拟环境
source .venv/bin/activate

# 启动 FastAPI 服务（会连接 PostgreSQL）
python src/run_service.py
```

**启动前端服务**（新终端）：

```bash
cd frontend

# 开发模式启动
npm run dev

# 或生产模式
npm run build
npm run preview
```

#### 验证服务状态

```bash
# 检查后端健康状态
curl http://localhost:8080/health

# 检查前端
# 浏览器访问 http://localhost:8501
```

## 📁 项目结构

```
KnowLedgeLib/
├── frontend/                 # Vue.js 前端
│   ├── src/
│   │   ├── api/            # API 调用封装
│   │   ├── components/      # Vue 组件
│   │   ├── pages/          # 页面组件
│   │   ├── stores/         # Pinia 状态管理
│   │   └── router/         # 路由配置
│   └── package.json
├── src/                    # Python 后端
│   ├── agents/            # LangGraph Agents
│   ├── client/            # 客户端封装
│   ├── core/              # 核心模块（LLM、配置）
│   ├── memory/            # 记忆系统（Checkpointer、Store）
│   ├── service/           # FastAPI 服务
│   └── run_service.py    # 服务入口
├── scripts/               # 脚本工具
│   ├── create_milvus_db.py  # 创建 Milvus 集合
│   ├── rbac_schema.sql       # RBAC 表结构
│   ├── rbac_seed_data.sql   # RBAC 初始数据
│   ├── text2sql_schema.sql   # Text2SQL 表结构
│   ├── text2sql_seed_data.sql # Text2SQL 初始数据
│   └── insert.py            # 文档导入脚本
├── data/                  # 数据目录
│   ├── db_descriptions.json  # 数据库表描述
│   ├── ddl_examples.json     # DDL 示例
│   ├── qsql_examples.json    # SQL 查询示例
│   ├── AI/                 # AI 相关文档（PDF）
│   ├── database/           # 数据库文档（PDF）
│   └── micro_service/     # 微服务文档（PDF）
├── infra/                 # 基础设施配置
│   ├── milvus/           # Milvus 配置（etcd、minio、standalone）
│   ├── mysql/             # MySQL 配置（权限管理用）
│   └── postgres/          # PostgreSQL 配置（记忆系统用）
├── docs/                  # 文档
│   ├── 记忆系统.md
│   ├── 权限控制.md
│   ├── 数据库设计.md
│   ├── UI界面.md
│   └── 接口规定.md
├── compose.yaml           # Docker Compose 配置
├── .env.example         # 环境变量示例
└── pyproject.toml        # Python 项目配置
```



## 🔐 权限管理说明

系统实现了基于 RBAC 的权限控制，详细说明请参考 [docs/权限控制.md](docs/权限控制.md)。

### 角色定义

- **管理员 (admin)**: 拥有所有权限，不受部门限制
- **数据分析师(analyst)**: 拥有rtext2sql的功能访问权限
- **普通用户 (member)**: 需要通过部门配置访问权限

### 部门权限

每个用户可以配置对不同部门的访问权限：
- **管理员权限**: 可以查看和编辑该部门的文档
- **只读权限**: 只能查看该部门的文档

### 权限管理界面

访问 `http://localhost:8501/permission` 可以管理用户权限。

## 📝 使用说明

### 用户登录

1. 访问系统首页
2. 输入用户名和密码
3. 首次登录需要注册账号

### 知识库问答

1. 进入"知识库"页面
2. 在对话框中输入问题
3. 系统会检索相关文档并生成回答
4. 支持多轮对话上下文

### 文件管理

1. 进入"文件管理"页面
2. 查看所有可访问的文档
3. 可以上传、下载、删除文件
4. 按部门筛选文件

### 权限管理（仅管理员）

1. 进入"权限控制"页面
2. 查看所有用户及其权限
3. 设置用户为部门管理员
4. 删除用户

## 🧪 测试

运行测试：

```bash
# 激活虚拟环境
source .venv/bin/activate

# 运行所有测试
pytest

# 运行特定测试
pytest tests/agents/test_agents.py

# 生成覆盖率报告
pytest --cov=src --cov-report=html
```

## 🐳 Docker 开发

使用 Docker Compose 进行开发：

```bash
# 启动所有服务
docker compose up

# 查看日志
docker compose logs -f

# 停止服务
docker compose down

# 重新构建
docker compose up --build
```

## 📖 相关文档

- [权限控制说明](docs/权限控制.md)
- [数据库设计](docs/数据库设计.md)
- [UI 界面说明](docs/UI界面.md)
- [API 接口规定](docs/接口规定.md)
- [RBAC 数据库迁移说明](docs/RBAC数据库迁移说明.md)



## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件。

## 💬 技术支持

如有问题或建议，请：
- 提交 [Issue](https://github.com/liver0377/KnowLedgeLib/issues)
- 发送邮件至项目维护者

## 🙏 致谢

感谢以下开源项目：

- [LangGraph](https://github.com/langchain-ai/langgraph)
- [FastAPI](https://fastapi.tiangolo.com/)
- [Vue.js](https://vuejs.org/)
- [Milvus](https://milvus.io/)
