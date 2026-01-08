-- ============================================================================
-- RBAC + ABAC 权限管理 - 初始化数据 (MySQL)
-- 
-- 此脚本需要在 rbac_schema.sql 执行之后运行
-- 包含：系统角色、权限点、角色权限映射、示例部门和用户
-- ============================================================================

USE knowledge_lib;

-- ============================================================================
-- 1. 初始化角色 (roles)
-- ============================================================================
INSERT INTO roles (role_key, name, description, priority, is_system) VALUES
('admin',   '管理员',  '拥有所有权限，不受部门限制',                    100, 1),
('editor',  '编辑者',  '可查看、下载、上传知识库文件，受部门限制',        50,  1),
('viewer',  '查看者',  '只能查看和下载知识库文件，受部门限制',            10,  1)
ON DUPLICATE KEY UPDATE 
    name = VALUES(name),
    description = VALUES(description),
    priority = VALUES(priority);


-- ============================================================================
-- 2. 初始化权限点 (permissions)
-- 权限标识采用 "资源:操作:子操作" 命名规范
-- ============================================================================
INSERT INTO permissions (perm_key, name, description, resource, action, is_system) VALUES
-- 知识库权限
('kb:file:list',      '知识库文件列表',   '列出知识库文件',              'kb',    'list',     1),
('kb:file:detail',    '知识库文件详情',   '查看知识库文件详情',          'kb',    'detail',   1),
('kb:file:download',  '知识库文件下载',   '下载知识库文件',              'kb',    'download', 1),
('kb:file:upload',    '知识库文件上传',   '上传/编辑知识库文件',         'kb',    'upload',   1),
('kb:file:delete',    '知识库文件删除',   '删除知识库文件',              'kb',    'delete',   1),
-- 管理员权限
('admin:user:list',   '用户列表',         '列出所有用户',                'admin', 'list',     1),
('admin:user:update', '用户更新',         '更新用户信息',                'admin', 'update',   1)
ON DUPLICATE KEY UPDATE 
    name = VALUES(name),
    description = VALUES(description),
    resource = VALUES(resource),
    action = VALUES(action);


-- ============================================================================
-- 3. 初始化角色-权限映射 (role_permissions)
-- 根据 auth.py 中的 ROLE_PERMS 映射关系
-- ============================================================================

-- 获取角色和权限的ID，然后插入映射关系
-- admin 角色拥有所有权限
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
CROSS JOIN permissions p
WHERE r.role_key = 'admin'
  AND p.perm_key IN (
      'kb:file:list', 'kb:file:detail', 'kb:file:download', 'kb:file:upload', 'kb:file:delete',
      'admin:user:list', 'admin:user:update'
  )
ON DUPLICATE KEY UPDATE role_id = role_id;

-- editor 角色拥有知识库相关权限
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
CROSS JOIN permissions p
WHERE r.role_key = 'editor'
  AND p.perm_key IN (
      'kb:file:list', 'kb:file:detail', 'kb:file:download', 'kb:file:upload', 'kb:file:delete'
  )
ON DUPLICATE KEY UPDATE role_id = role_id;

-- viewer 角色只有查看和下载权限
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
CROSS JOIN permissions p
WHERE r.role_key = 'viewer'
  AND p.perm_key IN (
      'kb:file:list', 'kb:file:detail', 'kb:file:download'
  )
ON DUPLICATE KEY UPDATE role_id = role_id;


-- ============================================================================
-- 4. 初始化示例部门 (departments)
-- 根据现有项目的知识库分类
-- ============================================================================
INSERT INTO departments (dept_key, name, description, is_active) VALUES
('AI',            'AI 部门',            '人工智能相关知识库',          1),
('micro_service', '微服务部门',         '微服务架构相关知识库',        1),
('database',      '数据库部门',         '数据库相关知识库',            1)
ON DUPLICATE KEY UPDATE 
    name = VALUES(name),
    description = VALUES(description);


-- ============================================================================
-- 5. 初始化示例用户 (users)
-- 密码使用 bcrypt 哈希 (示例密码: "password123")
-- 实际项目中请使用 Python 的 bcrypt 库生成哈希
-- ============================================================================
-- 注意: 以下密码哈希是示例，实际使用时需要用 bcrypt 生成
-- 示例密码 "password123" 的 bcrypt 哈希 (cost=12)

INSERT INTO users (username, password_hash, display_name, email, is_active) VALUES
('user-ryan',    '$2b$12$Mce8BpiT087DAw/p/FhHq.D5Bs4wPH128Y5S9drsIJl67tr', 'Ryan (管理员)',   'ryan@example.com',   1),
('user-editor',  '$2b$12$Mce8BpiT087DAw/p/FhHq.D5Bs4wPH128Y5S9drsIJl67tr', '编辑者用户',      'editor@example.com', 1),
('user-viewer',  '$2b$12$Mce8BpiT087DAw/p/FhHq.D5Bs4wPH128Y5S9drsIJl67tr', '查看者用户',      'viewer@example.com', 1)
ON DUPLICATE KEY UPDATE 
    display_name = VALUES(display_name),
    email = VALUES(email);


-- ============================================================================
-- 6. 初始化用户-角色映射 (user_roles)
-- ============================================================================
-- user-ryan -> admin
INSERT INTO user_roles (user_id, role_id)
SELECT u.id, r.id
FROM users u
CROSS JOIN roles r
WHERE u.username = 'user-ryan' AND r.role_key = 'admin'
ON DUPLICATE KEY UPDATE user_id = user_id;

-- user-editor -> editor
INSERT INTO user_roles (user_id, role_id)
SELECT u.id, r.id
FROM users u
CROSS JOIN roles r
WHERE u.username = 'user-editor' AND r.role_key = 'editor'
ON DUPLICATE KEY UPDATE user_id = user_id;

-- user-viewer -> viewer
INSERT INTO user_roles (user_id, role_id)
SELECT u.id, r.id
FROM users u
CROSS JOIN roles r
WHERE u.username = 'user-viewer' AND r.role_key = 'viewer'
ON DUPLICATE KEY UPDATE user_id = user_id;


-- ============================================================================
-- 7. 初始化用户-部门访问权限映射 (user_departments)
-- 根据原 _DEMO_ALLOWED_DEPT_KEYS 映射关系
-- ============================================================================
-- user-ryan (admin) -> micro_service (读写权限)
-- 注意: admin 角色在业务逻辑层不受部门限制，但这里仍可以设置默认部门
INSERT INTO user_departments (user_id, department_id, can_read, can_write)
SELECT u.id, d.id, 1, 1
FROM users u
CROSS JOIN departments d
WHERE u.username = 'user-ryan' AND d.dept_key = 'micro_service'
ON DUPLICATE KEY UPDATE can_read = VALUES(can_read), can_write = VALUES(can_write);

-- user-editor -> micro_service (读写权限), AI (只读权限)
INSERT INTO user_departments (user_id, department_id, can_read, can_write)
SELECT u.id, d.id, 1, 1
FROM users u
CROSS JOIN departments d
WHERE u.username = 'user-editor' AND d.dept_key = 'micro_service'
ON DUPLICATE KEY UPDATE can_read = VALUES(can_read), can_write = VALUES(can_write);

INSERT INTO user_departments (user_id, department_id, can_read, can_write)
SELECT u.id, d.id, 1, 0
FROM users u
CROSS JOIN departments d
WHERE u.username = 'user-editor' AND d.dept_key = 'AI'
ON DUPLICATE KEY UPDATE can_read = VALUES(can_read), can_write = VALUES(can_write);

-- user-viewer -> AI (只读权限)
INSERT INTO user_departments (user_id, department_id, can_read, can_write)
SELECT u.id, d.id, 1, 0
FROM users u
CROSS JOIN departments d
WHERE u.username = 'user-viewer' AND d.dept_key = 'AI'
ON DUPLICATE KEY UPDATE can_read = VALUES(can_read), can_write = VALUES(can_write);


-- ============================================================================
-- 验证数据插入结果
-- ============================================================================
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
SELECT u.username, d.dept_key, ud.can_read, ud.can_write
FROM users u
JOIN user_departments ud ON u.id = ud.user_id
JOIN departments d ON ud.department_id = d.id
ORDER BY u.username, d.dept_key;
