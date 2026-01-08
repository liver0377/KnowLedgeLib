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
- Docker & Docker Compose
- MySQL 8.0+
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

# 数据库配置
DATABASE_URL=mysql+aiomysql://user:password@localhost:3306/knowledgelib

# Milvus 配置
MILVUS_HOST=localhost
MILVUS_PORT=19530

# JWT 密钥（必须）
JWT_SECRET_KEY=your_secret_key_here

# LangSmith 追踪（可选）
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_langsmith_api_key
```

### 3. 启动 MySQL 服务

#### 使用 Docker 启动 MySQL

```bash
# 创建数据目录
mkdir -p data/mysql

# 启动 MySQL
docker run -d \
  --name mysql-server \
  -e MYSQL_ROOT_PASSWORD=rootpassword \
  -e MYSQL_DATABASE=knowledgelib \
  -e MYSQL_USER=knowledgelib \
  -e MYSQL_PASSWORD=knowledgelib123 \
  -p 3306:3306 \
  -v $(pwd)/data/mysql:/var/lib/mysql \
  mysql:8.0
```

或使用 Docker Compose：

```bash
# 使用 compose.yaml 启动
docker compose up -d mysql
```

#### 本地安装 MySQL

如果使用本地 MySQL，确保已安装并启动服务：

```bash
# Ubuntu/Debian
sudo apt-get install mysql-server
sudo systemctl start mysql

# macOS
brew install mysql
brew services start mysql

# Windows
# 下载并安装 MySQL Installer
```

### 4. 启动 Milvus 服务

#### 使用 Docker 启动 Milvus

```bash
# 下载 Milvus Compose 文件
wget https://github.com/milvus-io/milvus/releases/download/v2.3.4/milvus-standalone-docker-compose.yml -O docker-compose-milvus.yml

# 启动 Milvus
docker compose -f docker-compose-milvus.yml up -d
```

#### 验证 Milvus 运行状态

```bash
# 检查 Milvus 状态
curl http://localhost:19530/healthz

# 应返回：{"status":"ok"}
```

### 5. 导入数据库数据

#### 创建数据库表结构

```bash
# 确保已激活虚拟环境
source .venv/bin/activate

# 执行初始化脚本
python scripts/create_chroma_db.py
```

或手动执行 SQL：

```bash
# 登录 MySQL
mysql -u knowledgelib -p

# 执行建表脚本
source scripts/schema.sql

# 执行 RBAC 权限表
source scripts/rbac_schema.sql

# 导入初始数据
source scripts/insert.sql
source scripts/rbac_seed_data.sql
```

#### 数据库结构说明

- **users**: 用户表
- **roles**: 角色表
- **departments**: 部门表
- **user_departments**: 用户-部门关联表（包含权限信息）
- **user_roles**: 用户-角色关联表
- **kb_files**: 知识库文件表
- **files**: 文件存储表

详细表结构请参考 `docs/数据库设计.md` 和 `docs/RBAC数据库迁移说明.md`

### 6. 导入文档到向量数据库

#### 使用脚本导入

```bash
# 确保已激活虚拟环境
source .venv/bin/activate

# 导入文档到 Milvus
python scripts/insert.py
```

该脚本会：
1. 读取 `data/` 目录下的所有 PDF 文档
2. 使用 PDF 解析器提取文本内容
3. 分割文本为 chunks
4. 生成 embedding 向量
5. 存储到 Milvus 向量数据库

#### 手动添加文档

通过前端界面上传：
1. 访问 http://localhost:8501
2. 登录系统
3. 进入"文件管理"页面
4. 点击"上传文件"
5. 选择 PDF 文件并上传

### 7. 启动前后端服务

#### 使用 Docker Compose 启动（推荐）

```bash
# 启动所有服务
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

# 启动 FastAPI 服务
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
│   ├── service/           # FastAPI 服务
│   └── run_service.py    # 服务入口
├── scripts/               # 脚本工具
│   ├── create_chroma_db.py  # 创建数据库
│   ├── insert.sql         # SQL 初始化脚本
│   └── insert.py         # 文档导入脚本
├── data/                  # 数据目录
│   ├── AI/              # AI 部门文档
│   ├── database/         # 数据库部门文档
│   └── micro_service/    # 微服务部门文档
├── docs/                  # 文档
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

## 🤝 贡献指南

欢迎贡献！请遵循以下步骤：

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

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
- [ChromaDB](https://www.trychroma.com/)
