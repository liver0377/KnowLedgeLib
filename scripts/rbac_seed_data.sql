-- =============================================================================
-- RBAC + ABAC 权限管理 - 初始化数据 (MySQL)
-- 
-- 此脚本需要在 rbac_schema.sql 执行之后运行
-- 包含：系统角色、权限点、角色权限映射、示例部门和用户
-- 
-- 角色说明:
-- - 全局角色只有两种: admin 和 member
-- - 部门级别的权限通过 user_departments 表的 can_read 和 can_write 控制
-- =============================================================================

USE knowledge_lib;

-- =============================================================================
-- 清空现有数据（按外键依赖顺序）
-- =============================================================================
SET FOREIGN_KEY_CHECKS = 0;

DELETE FROM user_departments;
DELETE FROM user_roles;
DELETE FROM role_permissions;
DELETE FROM pending_users;
DELETE FROM audit_logs;
DELETE FROM users;
DELETE FROM roles;
DELETE FROM permissions;
DELETE FROM departments;

SET FOREIGN_KEY_CHECKS = 1;

-- 重置自增ID
ALTER TABLE users AUTO_INCREMENT = 1;
ALTER TABLE roles AUTO_INCREMENT = 1;
ALTER TABLE permissions AUTO_INCREMENT = 1;
ALTER TABLE departments AUTO_INCREMENT = 1;
ALTER TABLE user_roles AUTO_INCREMENT = 1;
ALTER TABLE role_permissions AUTO_INCREMENT = 1;
ALTER TABLE user_departments AUTO_INCREMENT = 1;
ALTER TABLE pending_users AUTO_INCREMENT = 1;
ALTER TABLE audit_logs AUTO_INCREMENT = 1;

-- =============================================================================
-- 1. 初始化角色 (roles)
-- 全局角色只有 admin 和 member
-- =============================================================================
INSERT INTO roles (role_key, name, description, priority, is_system) VALUES
('admin',   '管理员',  '拥有所有权限，不受部门限制',                    100, 1),
('member',  '普通用户', '普通用户，部门权限由 can_read 和 can_write 控制', 10,  1)
ON DUPLICATE KEY UPDATE 
    name = VALUES(name),
    description = VALUES(description),
    priority = VALUES(priority);


-- =============================================================================
-- 2. 初始化权限点 (permissions)
-- 权限标识采用 "资源:操作:子操作" 命名规范
-- =============================================================================
INSERT INTO permissions (perm_key, name, description, resource, action, is_system) VALUES
-- 知识库权限
('kb:file:list',      '知识库文件列表',   '列出知识库文件',              'kb',    'list',     1),
('kb:file:detail',    '知识库文件详情',   '查看知识库文件详情',          'kb',    'detail',   1),
('kb:file:download',  '知识库文件下载',   '下载知识库文件',              'kb',    'download', 1),
('kb:file:upload',    '知识库文件上传',   '上传/编辑知识库文件',         'kb',    'upload',   1),
('kb:file:delete',    '知识库文件删除',   '删除知识库文件',              'kb',    'delete',   1),
-- 管理员权限
('admin:user:list',   '用户列表',         '列出所有用户',                'admin', 'list',     1),
('admin:user:update', '用户更新',         '更新用户信息',                'admin', 'update',   1),
('admin:dept:create', '创建部门',         '创建新部门',                  'admin', 'create',   1)
ON DUPLICATE KEY UPDATE 
    name = VALUES(name),
    description = VALUES(description),
    resource = VALUES(resource),
    action = VALUES(action);


-- =============================================================================
-- 3. 初始化角色-权限映射 (role_permissions)
-- 根据 auth.py 中的 ROLE_PERMS 映射关系
-- =============================================================================

-- admin 角色拥有所有权限
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
CROSS JOIN permissions p
WHERE r.role_key = 'admin'
  AND p.perm_key IN (
      'kb:file:list', 'kb:file:detail', 'kb:file:download', 'kb:file:upload', 'kb:file:delete',
      'admin:user:list', 'admin:user:update', 'admin:dept:create'
  )
ON DUPLICATE KEY UPDATE role_id = role_id;

-- member 角色拥有基本的知识库权限（具体读写权限由部门级别控制）
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
CROSS JOIN permissions p
WHERE r.role_key = 'member'
  AND p.perm_key IN (
      'kb:file:list', 'kb:file:detail', 'kb:file:download', 'kb:file:upload', 'kb:file:delete'
  )
ON DUPLICATE KEY UPDATE role_id = role_id;


-- =============================================================================
-- 4. 初始化示例部门 (departments)
-- 根据现有项目的知识库分类
-- =============================================================================
INSERT INTO departments (dept_key, name, description, is_active) VALUES
('AI',            'AI 部门',            '人工智能相关知识库',          1),
('micro_service', '微服务部门',         '微服务架构相关知识库',        1),
('database',      '数据库部门',         '数据库相关知识库',            1)
ON DUPLICATE KEY UPDATE 
    name = VALUES(name),
    description = VALUES(description);


-- =============================================================================
-- 5. 初始化示例用户 (users)
-- 密码使用 bcrypt 哈希 (示例密码: "123456")
-- 实际项目中请使用 Python 的 bcrypt 库生成哈希
-- =============================================================================
-- 注意: 以下密码哈希是示例，实际使用时需要用 bcrypt 生成
-- 示例密码 "123456" 的 bcrypt 哈希 (cost=12)

INSERT INTO users (username, password_hash, display_name, email, is_active) VALUES
('user-ryan', '$2b$12$K1dNX0fh.jQl32k93V8n9eYDP/EzkNbyDsoa1lVL5fuJkWpmCcheC', 'Ryan (管理员)',   'ryan@example.com',   1),
('user1',       '$2b$12$K1dNX0fh.jQl32k93V8n9eYDP/EzkNbyDsoa1lVL5fuJkWpmCcheC', '普通用户1',       'user1@example.com',  1),
('user2',       '$2b$12$K1dNX0fh.jQl32k93V8n9eYDP/EzkNbyDsoa1lVL5fuJkWpmCcheC', '普通用户2',       'user2@example.com',  1)
ON DUPLICATE KEY UPDATE 
    display_name = VALUES(display_name),
    email = VALUES(email);


-- =============================================================================
-- 6. 初始化用户-角色映射 (user_roles)
-- 所有用户都是 member，user-ryan 同时也是 admin
-- =============================================================================
-- user-ryan -> admin + member
INSERT INTO user_roles (user_id, role_id)
SELECT u.id, r.id
FROM users u
CROSS JOIN roles r
WHERE u.username = 'user-ryan' AND r.role_key = 'admin'
ON DUPLICATE KEY UPDATE user_id = user_id;

INSERT INTO user_roles (user_id, role_id)
SELECT u.id, r.id
FROM users u
CROSS JOIN roles r
WHERE u.username = 'user-ryan' AND r.role_key = 'member'
ON DUPLICATE KEY UPDATE user_id = user_id;

-- user1 -> member
INSERT INTO user_roles (user_id, role_id)
SELECT u.id, r.id
FROM users u
CROSS JOIN roles r
WHERE u.username = 'user1' AND r.role_key = 'member'
ON DUPLICATE KEY UPDATE user_id = user_id;

-- user2 -> member
INSERT INTO user_roles (user_id, role_id)
SELECT u.id, r.id
FROM users u
CROSS JOIN roles r
WHERE u.username = 'user2' AND r.role_key = 'member'
ON DUPLICATE KEY UPDATE user_id = user_id;


-- =============================================================================
-- 7. 初始化用户-部门访问权限映射 (user_departments)
-- 部门权限通过 can_read 和 can_write 控制
-- - user-ryan (admin): 所有部门（读写权限），admin 不受部门限制但设置默认部门
-- - user1 (member): micro_service (读写权限), AI (只读权限)
-- - user2 (member): database (只读权限)
-- =============================================================================

-- user-ryan (admin) -> 所有部门 (读写权限)
-- 注意: admin 角色在业务逻辑层不受部门限制，但这里仍可以设置默认部门
INSERT INTO user_departments (user_id, department_id, can_read, can_write)
SELECT u.id, d.id, 1, 1
FROM users u
CROSS JOIN departments d
WHERE u.username = 'user-ryan'
ON DUPLICATE KEY UPDATE can_read = VALUES(can_read), can_write = VALUES(can_write);

-- user1 -> micro_service (读写权限, 相当于editor)
INSERT INTO user_departments (user_id, department_id, can_read, can_write)
SELECT u.id, d.id, 1, 1
FROM users u
CROSS JOIN departments d
WHERE u.username = 'user1' AND d.dept_key = 'micro_service'
ON DUPLICATE KEY UPDATE can_read = VALUES(can_read), can_write = VALUES(can_write);

-- user1 -> AI (只读权限, 相当于viewer)
INSERT INTO user_departments (user_id, department_id, can_read, can_write)
SELECT u.id, d.id, 1, 0
FROM users u
CROSS JOIN departments d
WHERE u.username = 'user1' AND d.dept_key = 'AI'
ON DUPLICATE KEY UPDATE can_read = VALUES(can_read), can_write = VALUES(can_write);

-- user2 -> database (只读权限, 相当于viewer)
INSERT INTO user_departments (user_id, department_id, can_read, can_write)
SELECT u.id, d.id, 1, 0
FROM users u
CROSS JOIN departments d
WHERE u.username = 'user2' AND d.dept_key = 'database'
ON DUPLICATE KEY UPDATE can_read = VALUES(can_read), can_write = VALUES(can_write);


-- =============================================================================
-- 验证数据插入结果
-- =============================================================================
SELECT '--- 角色列表 ---' AS info;
SELECT id, role_key, name, priority FROM roles ORDER BY priority DESC;

SELECT '--- 权限列表 ---' AS info;
SELECT id, perm_key, name, resource FROM permissions ORDER BY resource, action;

SELECT '--- 角色权限映射 ---' AS info;
SELECT r.role_key, GROUP_CONCAT(p.perm_key ORDER BY p.perm_key SEPARATOR ', ') AS permissions
FROM roles r
JOIN role_permissions rp ON r.id = rp.role_id
JOIN permissions p ON rp.permission_id = p.id
GROUP BY r.id, r.role_key
ORDER BY r.priority DESC;

SELECT '--- 部门列表 ---' AS info;
SELECT id, dept_key, name FROM departments;

SELECT '--- 用户列表 ---' AS info;
SELECT id, username, display_name, is_active FROM users;

SELECT '--- 用户角色映射 ---' AS info;
SELECT u.username, r.role_key, r.name AS role_name
FROM users u
JOIN user_roles ur ON u.id = ur.user_id
JOIN roles r ON ur.role_id = r.id
ORDER BY u.username;

SELECT '--- 用户部门访问权限 ---' AS info;
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
