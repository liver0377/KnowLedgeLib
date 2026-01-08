-- ============================================================================
-- 添加用户审批功能
-- 创建待审批用户表
-- ============================================================================

USE knowledge_lib;

-- ============================================================================
-- 待审批用户表 (pending_users)
-- 存储待审批的用户注册申请
-- ============================================================================
CREATE TABLE IF NOT EXISTS pending_users (
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
    review_comment   VARCHAR(500)    DEFAULT NULL COMMENT '审批意见',
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    
    INDEX idx_pending_users_status (status),
    INDEX idx_pending_users_username (username),
    CONSTRAINT fk_pending_users_reviewed_by FOREIGN KEY (reviewed_by) REFERENCES users(id) ON DELETE SET NULL,
    CONSTRAINT fk_pending_users_requested_dept FOREIGN KEY (requested_dept_id) REFERENCES departments(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='待审批用户表';

-- 添加备注
ALTER TABLE pending_users COMMENT = '待审批用户表 - 存储用户注册申请，等待管理员审批';
