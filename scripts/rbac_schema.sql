-- =============================================================================
-- RBAC + ABAC 权限管理数据库 Schema (MySQL)
--
-- 设计说明:
-- - RBAC: 基于角色的访问控制 (Role-Based Access Control)
-- - ABAC: 基于部门属性的访问控制 (Attribute-Based Access Control)
-- - 全局角色只有两种: admin 和 member（普通用户）
-- - 部门权限通过 user_departments 表的 can_read 和 can_write 控制
-- =============================================================================

-- 如果数据库不存在则创建
CREATE DATABASE IF NOT EXISTS knowledge_lib DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE knowledge_lib;

-- -----------------------------------------------------------------------------
-- 0. 先删除视图（依赖表,必须先删）
-- -----------------------------------------------------------------------------
DROP VIEW IF EXISTS v_user_dept_access;
DROP VIEW IF EXISTS v_user_permissions;

-- -----------------------------------------------------------------------------
-- 0. 再按依赖顺序删除表（先子表/依赖表,再父表）
-- -----------------------------------------------------------------------------
DROP TABLE IF EXISTS audit_logs;
DROP TABLE IF EXISTS pending_users;
DROP TABLE IF EXISTS user_departments;
DROP TABLE IF EXISTS role_permissions;
DROP TABLE IF EXISTS user_roles;
DROP TABLE IF EXISTS permissions;
DROP TABLE IF EXISTS roles;
DROP TABLE IF EXISTS departments;
DROP TABLE IF EXISTS users;

-- ============================================================================
-- 1. 用户表 (users)
-- ============================================================================
CREATE TABLE users (
    id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    username        VARCHAR(64)     NOT NULL UNIQUE COMMENT '用户名/登录账号',
    password_hash   VARCHAR(255)    NOT NULL COMMENT '密码哈希值',
    display_name    VARCHAR(128)    DEFAULT NULL COMMENT '显示名称',
    email           VARCHAR(255)    DEFAULT NULL COMMENT '邮箱',
    is_active       TINYINT(1)      NOT NULL DEFAULT 1 COMMENT '是否启用: 1=启用, 0=禁用',
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

    INDEX idx_users_username (username),
    INDEX idx_users_is_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户表';

-- ============================================================================
-- 2. 角色表 (roles)
-- ============================================================================
CREATE TABLE roles (
    id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    role_key        VARCHAR(32)     NOT NULL UNIQUE COMMENT '角色标识: admin, member',
    name            VARCHAR(64)     NOT NULL COMMENT '角色名称',
    description     VARCHAR(255)    DEFAULT NULL COMMENT '角色描述',
    priority        INT             NOT NULL DEFAULT 0 COMMENT '优先级,数字越大优先级越高',
    is_system       TINYINT(1)      NOT NULL DEFAULT 0 COMMENT '是否系统内置角色: 1=是, 0=否',
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

    INDEX idx_roles_role_key (role_key),
    INDEX idx_roles_priority (priority)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='角色表';

-- ============================================================================
-- 3. 权限表 (permissions)
-- ============================================================================
CREATE TABLE permissions (
    id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    perm_key        VARCHAR(64)     NOT NULL UNIQUE COMMENT '权限标识: kb:file:list, admin:user:update 等',
    name            VARCHAR(128)    NOT NULL COMMENT '权限名称',
    description     VARCHAR(255)    DEFAULT NULL COMMENT '权限描述',
    resource        VARCHAR(32)     NOT NULL COMMENT '资源类型: kb, admin 等',
    action          VARCHAR(32)     NOT NULL COMMENT '操作类型: list, detail, upload 等',
    is_system       TINYINT(1)      NOT NULL DEFAULT 0 COMMENT '是否系统内置权限: 1=是, 0=否',
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

    INDEX idx_permissions_perm_key (perm_key),
    INDEX idx_permissions_resource (resource)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='权限表';

-- ============================================================================
-- 4. 部门表 (departments)
-- ============================================================================
CREATE TABLE departments (
    id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    dept_key        VARCHAR(64)     NOT NULL UNIQUE COMMENT '部门标识: AI, micro_service 等',
    name            VARCHAR(128)    NOT NULL COMMENT '部门名称',
    description     VARCHAR(255)    DEFAULT NULL COMMENT '部门描述',
    parent_id       BIGINT UNSIGNED DEFAULT NULL COMMENT '父部门ID,用于部门层级',
    is_active       TINYINT(1)      NOT NULL DEFAULT 1 COMMENT '是否启用: 1=启用, 0=禁用',
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

    INDEX idx_departments_dept_key (dept_key),
    INDEX idx_departments_parent_id (parent_id),
    CONSTRAINT fk_departments_parent FOREIGN KEY (parent_id) REFERENCES departments(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='部门表';

-- ============================================================================
-- 5. 用户-角色关联表 (user_roles)
-- ============================================================================
CREATE TABLE user_roles (
    id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id         BIGINT UNSIGNED NOT NULL COMMENT '用户ID',
    role_id         BIGINT UNSIGNED NOT NULL COMMENT '角色ID',
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',

    UNIQUE KEY uk_user_role (user_id, role_id),
    INDEX idx_user_roles_user_id (user_id),
    INDEX idx_user_roles_role_id (role_id),
    CONSTRAINT fk_user_roles_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_user_roles_role FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户角色关联表';

-- ============================================================================
-- 6. 角色-权限关联表 (role_permissions)
-- ============================================================================
CREATE TABLE role_permissions (
    id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    role_id         BIGINT UNSIGNED NOT NULL COMMENT '角色ID',
    permission_id   BIGINT UNSIGNED NOT NULL COMMENT '权限ID',
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',

    UNIQUE KEY uk_role_permission (role_id, permission_id),
    INDEX idx_role_permissions_role_id (role_id),
    INDEX idx_role_permissions_permission_id (permission_id),
    CONSTRAINT fk_role_permissions_role FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE,
    CONSTRAINT fk_role_permissions_permission FOREIGN KEY (permission_id) REFERENCES permissions(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='角色权限关联表';

-- ============================================================================
-- 7. 用户-部门关联表 (user_departments)
-- ============================================================================
CREATE TABLE user_departments (
    id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id         BIGINT UNSIGNED NOT NULL COMMENT '用户ID',
    department_id   BIGINT UNSIGNED NOT NULL COMMENT '部门ID',
    can_read        TINYINT(1)      NOT NULL DEFAULT 1 COMMENT '是否可读: 1=是, 0=否',
    can_write       TINYINT(1)      NOT NULL DEFAULT 0 COMMENT '是否可写: 1=是, 0=否',
    dept_role       VARCHAR(20)     NOT NULL DEFAULT 'viewer' COMMENT '部门角色: viewer=只读, editor=可编辑',
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

    UNIQUE KEY uk_user_department (user_id, department_id),
    INDEX idx_user_departments_user_id (user_id),
    INDEX idx_user_departments_department_id (department_id),
    INDEX idx_user_departments_dept_role (dept_role),
    CONSTRAINT fk_user_departments_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_user_departments_department FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户部门关联表';

-- ============================================================================
-- 8. 待审批用户表 (pending_users)
-- ============================================================================
CREATE TABLE pending_users (
    id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    username        VARCHAR(64)     NOT NULL UNIQUE COMMENT '用户名',
    password_hash   VARCHAR(255)    NOT NULL COMMENT '密码哈希值',
    display_name    VARCHAR(128)    NOT NULL COMMENT '显示名称',
    email           VARCHAR(255)    DEFAULT NULL COMMENT '邮箱',
    requested_dept_id BIGINT UNSIGNED DEFAULT NULL COMMENT '申请的部门ID',
    reason          TEXT            DEFAULT NULL COMMENT '申请理由',
    status          VARCHAR(20)     NOT NULL DEFAULT 'pending' COMMENT '状态: pending=待审批, approved=已通过, rejected=已驳回',
    reviewed_by     BIGINT UNSIGNED DEFAULT NULL COMMENT '审批人ID',
    reviewed_at     DATETIME        DEFAULT NULL COMMENT '审批时间',
    review_comment  VARCHAR(500)    DEFAULT NULL COMMENT '审批意见',
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

    INDEX idx_pending_users_status (status),
    INDEX idx_pending_users_username (username),
    CONSTRAINT fk_pending_users_reviewed_by FOREIGN KEY (reviewed_by) REFERENCES users(id) ON DELETE SET NULL,
    CONSTRAINT fk_pending_users_requested_dept FOREIGN KEY (requested_dept_id) REFERENCES departments(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='待审批用户表';

-- ============================================================================
-- 9. [可选] 操作审计日志表 (audit_logs)
-- ============================================================================
CREATE TABLE audit_logs (
    id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id         BIGINT UNSIGNED DEFAULT NULL COMMENT '操作用户ID',
    username        VARCHAR(64)     DEFAULT NULL COMMENT '操作用户名',
    action          VARCHAR(64)     NOT NULL COMMENT '操作类型: login, logout, upload, download 等',
    resource_type   VARCHAR(64)     DEFAULT NULL COMMENT '资源类型: file, user, role 等',
    resource_id     VARCHAR(128)    DEFAULT NULL COMMENT '资源ID',
    dept_key        VARCHAR(64)     DEFAULT NULL COMMENT '涉及的部门',
    ip_address      VARCHAR(45)     DEFAULT NULL COMMENT '客户端IP地址',
    user_agent      VARCHAR(512)    DEFAULT NULL COMMENT '客户端User-Agent',
    request_path    VARCHAR(255)    DEFAULT NULL COMMENT '请求路径',
    request_method  VARCHAR(10)     DEFAULT NULL COMMENT '请求方法',
    status_code     INT             DEFAULT NULL COMMENT 'HTTP状态码',
    detail          JSON            DEFAULT NULL COMMENT '操作详情(JSON格式)',
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',

    INDEX idx_audit_logs_user_id (user_id),
    INDEX idx_audit_logs_action (action),
    INDEX idx_audit_logs_resource_type (resource_type),
    INDEX idx_audit_logs_created_at (created_at),
    INDEX idx_audit_logs_dept_key (dept_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='操作审计日志表';

-- ============================================================================
-- 视图: 用户完整权限视图 (v_user_permissions)
-- ============================================================================
CREATE OR REPLACE VIEW v_user_permissions AS
SELECT
    u.id AS user_id,
    u.username,
    r.role_key,
    r.name AS role_name,
    p.perm_key,
    p.name AS perm_name,
    p.resource,
    p.action
FROM users u
JOIN user_roles ur ON u.id = ur.user_id
JOIN roles r ON ur.role_id = r.id
JOIN role_permissions rp ON r.id = rp.role_id
JOIN permissions p ON rp.permission_id = p.id
WHERE u.is_active = 1;

-- ============================================================================
-- 视图: 用户部门访问权限视图 (v_user_dept_access)
-- ============================================================================
CREATE OR REPLACE VIEW v_user_dept_access AS
SELECT
    u.id AS user_id,
    u.username,
    d.dept_key,
    d.name AS dept_name,
    ud.can_read,
    ud.can_write
FROM users u
JOIN user_departments ud ON u.id = ud.user_id
JOIN departments d ON ud.department_id = d.id
WHERE u.is_active = 1 AND d.is_active = 1;
