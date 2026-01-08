# RBAC 数据库迁移说明

本文档说明如何从旧的权限系统（editor/viewer作为全局角色）迁移到新的权限系统（editor/viewer作为部门级别权限，全局只有admin和member）。

---

## 一、迁移概述

### 旧系统架构
- 全局角色：`admin`, `editor`, `viewer`
- 部门权限：通过 `allowed_dept_keys` 控制
- editor/viewer 是全局角色，拥有固定的知识库权限

### 新系统架构
- 全局角色：`admin`, `member`
- 部门权限：通过 `user_departments` 表的 `can_read` 和 `can_write` 字段控制
- editor/viewer 不再是全局角色，而是部门级别的权限

---

## 二、迁移步骤

### 步骤 1: 备份数据库

在执行任何迁移操作之前，**务必先备份数据库**。

```bash
# MySQL 备份命令示例
mysqldump -u your_username -p knowledge_lib > backup_$(date +%Y%m%d_%H%M%S).sql
```

### 步骤 2: 更新数据库 Schema

执行新的 schema 文件：

```bash
mysql -u your_username -p knowledge_lib < scripts/rbac_schema.sql
```

### 步骤 3: 初始化新数据

执行新的 seed data 文件：

```bash
mysql -u your_username -p knowledge_lib < scripts/rbac_seed_data.sql
```

### 步骤 4: 迁移用户角色

将所有 `editor` 和 `viewer` 角色用户改为 `member` 角色：

```sql
-- 更新 user_roles 表，将 editor 和 viewer 角色改为 member
UPDATE user_roles ur
JOIN roles r ON ur.role_id = r.id
SET ur.role_id = (SELECT id FROM roles WHERE role_key = 'member')
WHERE r.role_key IN ('editor', 'viewer');

-- 验证迁移结果
SELECT u.username, r.role_key
FROM users u
JOIN user_roles ur ON u.id = ur.user_id
JOIN roles r ON ur.role_id = r.id
ORDER BY u.username;
```

### 步骤 5: 迁移部门权限

根据用户之前的角色，设置 `user_departments` 表中的读写权限：

```sql
-- 为之前有 editor 角色的用户设置部门写权限
-- 假设这些用户已经可以访问某些部门（通过 allowed_dept_keys）
-- 这里需要根据实际的业务逻辑调整

-- 示例：如果用户之前是 editor，在所有已授权的部门设置 can_write=1
UPDATE user_departments ud
JOIN user_roles ur ON ud.user_id = ur.user_id
JOIN roles r ON ur.role_id = r.id
SET ud.can_write = 1
WHERE r.role_key IN ('admin', 'editor');

-- 为之前有 viewer 角色的用户确保只有读权限
-- 注意：这些用户之前就不能写，所以 can_write 应该已经是 0
-- 这里主要是确保一致性
```

**重要提示**：
- 如果系统之前没有使用 `allowed_dept_keys`，而是通过其他方式控制部门访问，需要根据实际情况调整迁移脚本
- `admin` 用户不受部门限制，但数据库中仍应保留部门记录作为默认值

### 步骤 6: 清理旧角色

删除 `editor` 和 `viewer` 角色记录：

```sql
-- 删除 editor 和 viewer 角色（确保没有用户还在使用这些角色）
DELETE FROM roles WHERE role_key IN ('editor', 'viewer');
```

### 步骤 7: 验证迁移结果

```sql
-- 1. 检查角色列表（应该只有 admin 和 member）
SELECT * FROM roles ORDER BY priority DESC;

-- 2. 检查用户角色（所有用户应该只有 admin 和 member）
SELECT u.username, GROUP_CONCAT(r.role_key) AS roles
FROM users u
JOIN user_roles ur ON u.id = ur.user_id
JOIN roles r ON ur.role_id = r.id
GROUP BY u.id, u.username
ORDER BY u.username;

-- 3. 检查用户部门权限
SELECT u.username, d.dept_key, ud.can_read, ud.can_write,
    CASE 
        WHEN ud.can_read = 1 AND ud.can_write = 1 THEN 'editor'
        WHEN ud.can_read = 1 AND ud.can_write = 0 THEN 'viewer'
        ELSE 'no access'
    END AS dept_role
FROM users u
JOIN user_departments ud ON u.id = ud.user_id
JOIN departments d ON ud.department_id = d.id
ORDER BY u.username, d.dept_key;
```

---

## 三、完整迁移脚本

将以下 SQL 保存为 `migrate_to_new_rbac.sql`，然后一次性执行：

```sql
-- =============================================================================
-- RBAC 数据库迁移脚本
-- 从旧的权限系统迁移到新的权限系统
-- =============================================================================

USE knowledge_lib;

-- 步骤 1: 更新用户角色（editor/viewer -> member）
UPDATE user_roles ur
JOIN roles r ON ur.role_id = r.id
SET ur.role_id = (SELECT id FROM roles WHERE role_key = 'member')
WHERE r.role_key IN ('editor', 'viewer');

-- 步骤 2: 为之前的 editor 角色用户设置部门写权限
UPDATE user_departments ud
JOIN user_roles ur ON ud.user_id = ur.user_id
JOIN roles r ON ur.role_id = r.id
SET ud.can_write = 1
WHERE r.role_key IN ('admin', 'editor');

-- 步骤 3: 验证迁移结果
SELECT '--- 角色列表 ---' AS info;
SELECT id, role_key, name, priority FROM roles ORDER BY priority DESC;

SELECT '--- 用户角色映射 ---' AS info;
SELECT u.id AS user_id, u.username, r.role_key, r.name AS role_name
FROM users u
JOIN user_roles ur ON u.id = ur.user_id
JOIN roles r ON ur.role_id = r.id
ORDER BY u.username;

SELECT '--- 用户部门访问权限 ---' AS info;
SELECT u.id AS user_id, u.username, d.dept_key, ud.can_read, ud.can_write,
    CASE 
        WHEN ud.can_read = 1 AND ud.can_write = 1 THEN 'editor'
        WHEN ud.can_read = 1 AND ud.can_write = 0 THEN 'viewer'
        ELSE 'no access'
    END AS dept_role
FROM users u
JOIN user_departments ud ON u.id = ud.user_id
JOIN departments d ON ud.department_id = d.id
ORDER BY u.username, d.dept_key;

-- 步骤 4: 删除旧角色（确保没有用户在使用）
-- 取消注释以下语句执行删除
-- DELETE FROM roles WHERE role_key IN ('editor', 'viewer');
```

执行迁移脚本：

```bash
mysql -u your_username -p knowledge_lib < migrate_to_new_rbac.sql
```

---

## 四、迁移后操作

### 1. 重启后端服务

```bash
# 停止服务
# 启动服务
python src/run_service.py
```

### 2. 测试登录

使用测试账号登录，验证 token 中的 roles 字段是否正确：

```bash
# 测试 admin 用户
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "user-ryan", "password": "password123"}'

# 测试 member 用户
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "user-editor", "password": "password123"}'
```

### 3. 测试权限

测试以下操作，确保权限控制正常：

- [ ] 管理员可以访问所有部门
- [ ] 普通用户只能访问有读权限的部门
- [ ] 普通用户只能上传到有写权限的部门
- [ ] 无权限时返回 403 或 404
- [ ] 前端权限显示正确

---

## 五、常见问题

### Q1: 迁移后用户无法登录？

**A**: 检查以下几点：
1. 确认 `user_roles` 表中用户角色的 `role_key` 是 `admin` 或 `member`
2. 确认 JWT token 中的 `roles` 字段只包含有效的角色
3. 查看后端日志，确认错误信息

### Q2: 部门权限不正确？

**A**: 检查以下几点：
1. 确认 `user_departments` 表中 `can_read` 和 `can_write` 的值是否正确
2. 确认后端的 `can_access_dept()` 和 `can_write_dept()` 函数正常工作
3. 查看数据库查询日志，确认权限检查逻辑

### Q3: 如何批量设置用户部门权限？

**A**: 可以通过以下方式批量设置：

```sql
-- 为特定用户设置多个部门的权限
INSERT INTO user_departments (user_id, department_id, can_read, can_write)
VALUES 
    (user_id_1, dept_id_1, 1, 1),
    (user_id_1, dept_id_2, 1, 0),
    (user_id_2, dept_id_1, 1, 1)
ON DUPLICATE KEY UPDATE 
    can_read = VALUES(can_read), 
    can_write = VALUES(can_write);
```

或者通过后端管理界面批量操作（如果有的话）。

---

## 六、回滚方案

如果迁移后出现问题，可以使用备份回滚：

```bash
# 恢复数据库
mysql -u your_username -p knowledge_lib < backup_YYYYMMDD_HHMMSS.sql
```

---

## 七、联系人

如果在迁移过程中遇到问题，请联系：

- 技术支持：[技术支持邮箱]
- GitHub Issues: [项目 GitHub 地址]

---

## 八、迁移检查清单

在完成迁移后，请确认以下事项：

- [ ] 数据库已备份
- [ ] 新的 schema 已执行
- [ ] 新的 seed data 已执行
- [ ] 用户角色已更新（editor/viewer -> member）
- [ ] 部门权限已正确设置（can_read/can_write）
- [ ] 旧角色已删除（editor/viewer）
- [ ] 后端服务已重启
- [ ] 用户登录功能正常
- [ ] 部门访问权限正常
- [ ] 文件上传/下载权限正常
- [ ] 前端权限显示正常
- [ ] 管理员权限正常
- [ ] 所有测试用例通过

---

## 九、迁移时间估算

- 数据库备份：5 分钟
- Schema 更新：2 分钟
- Seed data 初始化：1 分钟
- 用户角色迁移：2 分钟
- 部门权限迁移：5-10 分钟（取决于数据量）
- 验证测试：10-15 分钟

**总计：约 25-35 分钟**

---

## 十、注意事项

1. **数据一致性**: 迁移前请确认数据库中没有脏数据
2. **停机时间**: 建议在业务低峰期执行迁移，避免影响用户
3. **测试环境**: 建议先在测试环境验证迁移脚本，再在生产环境执行
4. **日志记录**: 迁移过程中请保留所有日志，便于问题排查
5. **用户通知**: 迁移完成后，建议通知用户可能需要重新登录

---

*最后更新时间：2026-01-08*
