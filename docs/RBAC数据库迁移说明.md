# RBAC权限系统数据库迁移说明

## 概述

本次更新将权限系统从硬编码改为使用MySQL数据库，实现了完整的RBAC（基于角色的访问控制）和ABAC（基于属性的访问控制）功能。

## 改动内容

### 1. 数据库配置

#### docker-compose.yml (`infra/mysql/docker-compose.yml`)
- 修改数据库名称：`ecommerce` → `knowledge_lib`
- 移除了`MYSQL_USER`和`MYSQL_PASSWORD`配置（使用root用户）
- 保留`MYSQL_ROOT_PASSWORD: rootpass`

#### 环境变量 (`.env`)
新增MySQL配置项：
```env
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=rootpass
MYSQL_DB=knowledge_lib
```

### 2. 新增文件

#### `src/service/db.py`
- 实现MySQL数据库连接管理
- 提供`RBACDAO`类封装所有数据库操作
- 包含以下方法：
  - `get_user_by_username()` - 根据用户名获取用户信息
  - `get_user_roles()` - 获取用户角色
  - `get_user_permissions()` - 获取用户权限点
  - `get_user_departments()` - 获取用户可访问部门
  - `list_all_users()` - 列出所有用户（管理员用）
  - `update_user_roles()` - 更新用户角色
  - `verify_password()` - 密码验证

### 3. 修改文件

#### `src/core/settings.py`
新增MySQL配置字段：
```python
MYSQL_HOST: str = Field(default="")
MYSQL_PORT: Optional[int] = Field(default=3306)
MYSQL_USER: str = Field(default="")
MYSQL_PASSWORD: SecretStr = Field(default="")
MYSQL_DB: str = Field(default="knowledge_lib")
MYSQL_CHARSET: str = Field(default="utf8mb4")
```

#### `src/service/auth.py`
**删除的内容：**
- 硬编码的`ROLE_PERMS`字典
- 硬编码的`_DEMO_ALLOWED_DEPT_KEYS`字典

**修改的内容：**
- `get_user_context()` - 从数据库加载用户权限和部门访问权限
- `require_perm()` - 从数据库查询用户权限集合
- `can_access_dept()` - 从数据库查询用户可访问的部门
- `can_upload_dept()` - 从数据库查询用户的部门写权限

**保留的内容：**
- 角色常量（`ROLE_ADMIN`, `ROLE_EDITOR`, `ROLE_VIEWER`）
- 权限点常量（用于代码中引用）
- JWT token生成和解析逻辑

#### `src/service/service.py`

**登录接口 (`/auth/login`)：**
- 删除硬编码的`_demo_users`字典
- 改用`RBACDAO.get_user_by_username()`从数据库查询用户
- 使用`RBACDAO.verify_password()`验证密码
- 使用`RBACDAO.get_user_roles()`获取用户角色

**用户列表接口 (`/admin/users`)：**
- 删除硬编码用户列表
- 改用`RBACDAO.list_all_users()`从数据库获取

**更新用户权限接口 (`/admin/users/{user_id}/permissions`)：**
- 改用`RBACDAO.update_user_roles()`更新数据库

## 数据库Schema

数据库表结构定义在以下文件中：
- `scripts/rbac_schema.sql` - 数据库表结构
- `scripts/rbac_seed_data.sql` - 初始化数据

### 核心表

1. **users** - 用户表
2. **roles** - 角色表
3. **permissions** - 权限点表
4. **departments** - 部门表
5. **user_roles** - 用户-角色关联表
6. **role_permissions** - 角色-权限关联表
7. **user_departments** - 用户-部门关联表（支持读/写权限）
8. **audit_logs** - 审计日志表（可选）

### 视图

1. **v_user_permissions** - 用户完整权限视图
2. **v_user_dept_access** - 用户部门访问权限视图

## 初始化数据

种子数据包含：
- 3个角色：admin, editor, viewer
- 6个权限点：kb:file:list, kb:file:detail, kb:file:download, kb:file:upload, admin:user:list, admin:user:update
- 3个示例部门：AI, micro_service, database
- 3个示例用户：
  - user-ryan (admin) - 拥有所有权限
  - user-editor (editor) - 拥有知识库相关权限
  - user-viewer (viewer) - 只有查看和下载权限

## 部署步骤

### 1. 启动MySQL容器

```bash
cd infra/mysql
docker-compose up -d
```

### 2. 执行数据库初始化脚本

```bash
# 连接到MySQL容器
docker exec -it knowledge-mysql mysql -uroot -prootpass

# 或者直接执行SQL文件
docker exec -i knowledge-mysql mysql -uroot -prootpass < scripts/rbac_schema.sql
docker exec -i knowledge-mysql mysql -uroot -prootpass knowledge_lib < scripts/rbac_seed_data.sql
```

### 3. 验证数据库连接

启动服务，检查日志中是否有MySQL连接成功的消息：
```bash
python src/run_service.py
```

应该看到类似日志：
```
INFO:service.db:MySQL connection pool created: 127.0.0.1:3306/knowledge_lib
```

### 4. 测试登录

使用示例用户登录（密码为：password123）：
- user-ryan (管理员)
- user-editor (编辑者)
- user-viewer (查看者)

```bash
curl -X POST http://localhost:8080/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "user-ryan", "password": "password123"}'
```

## 功能测试

### 1. 用户登录测试
```bash
# 使用admin用户登录
curl -X POST http://localhost:8080/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "user-ryan", "password": "password123"}' \
  -c cookies.txt

# 查看当前用户信息
curl http://localhost:8080/auth/me -b cookies.txt
```

### 2. 权限验证测试
```bash
# 测试知识库文件列表（需要kb:file:list权限）
curl http://localhost:8080/kb/files -b cookies.txt

# 测试用户列表（需要admin:user:list权限，只有admin可以访问）
curl http://localhost:8080/admin/users -b cookies.txt
```

### 3. 部门访问权限测试
```bash
# 使用viewer用户登录（只能访问AI部门）
curl -X POST http://localhost:8080/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "user-viewer", "password": "password123"}' \
  -c viewer_cookies.txt

# 测试访问AI部门的文件（应该成功）
curl http://localhost:8080/kb/files?dept_key=AI -b viewer_cookies.txt

# 测试访问micro_service部门的文件（应该失败或返回空列表）
curl http://localhost:8080/kb/files?dept_key=micro_service -b viewer_cookies.txt
```

### 4. 用户权限更新测试
```bash
# 更新用户角色（需要admin权限）
curl -X POST http://localhost:8080/admin/users/2/permissions \
  -H "Content-Type: application/json" \
  -d '{"roles": ["admin", "editor"]}' \
  -b cookies.txt
```

## 数据库操作

### 添加新用户

```sql
INSERT INTO users (username, password_hash, display_name, email, is_active)
VALUES ('newuser', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.uQxB3z3E8TBZOe', '新用户', 'new@example.com', 1);

-- 分配角色
INSERT INTO user_roles (user_id, role_id)
SELECT (SELECT id FROM users WHERE username = 'newuser'), id FROM roles WHERE role_key = 'viewer';
```

### 添加新权限

```sql
INSERT INTO permissions (perm_key, name, description, resource, action, is_system)
VALUES ('kb:file:delete', '删除文件', '删除知识库文件', 'kb', 'delete', 1);

-- 分配给admin角色
INSERT INTO role_permissions (role_id, permission_id)
SELECT id FROM roles WHERE role_key = 'admin',
SELECT id FROM permissions WHERE perm_key = 'kb:file:delete';
```

### 查询用户权限

```sql
-- 查询用户的所有权限
SELECT u.username, r.role_key, p.perm_key
FROM users u
JOIN user_roles ur ON u.id = ur.user_id
JOIN roles r ON ur.role_id = r.id
JOIN role_permissions rp ON r.id = rp.role_id
JOIN permissions p ON rp.permission_id = p.id
WHERE u.username = 'user-ryan';
```

## 注意事项

1. **密码哈希**：种子数据中的密码是`password123`的bcrypt哈希值。创建新用户时需要使用相同的哈希算法：
   ```python
   from passlib.context import CryptContext
   pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
   hashed_password = pwd_context.hash("your_password")
   ```

2. **数据库连接**：每次数据库操作都会创建新连接，确保MySQL容器正常运行且端口3306可访问。

3. **权限检查失败**：如果数据库查询失败，系统会使用空权限（安全第一），建议检查日志。

4. **Docker网络**：如果服务运行在Docker容器中，需要使用`host.docker.internal`代替`127.0.0.1`。

## 回滚方案

如果需要回滚到硬编码版本：

1. 恢复`src/service/auth.py`中的硬编码数据
2. 恢复`src/service/service.py`中的`_demo_users`字典
3. 删除`src/service/db.py`文件
4. 从`.env`中移除MySQL配置

## 后续优化建议

1. **连接池**：考虑使用`DBUtils`或`SQLAlchemy`实现真正的连接池
2. **缓存**：对用户权限等不常变化的数据添加缓存（Redis）
3. **审计日志**：启用`audit_logs`表记录关键操作
4. **密码重置**：添加密码重置功能
5. **用户注册**：添加用户注册接口（如果需要）
6. **部门层级**：支持部门层级结构（已设计parent_id字段）
