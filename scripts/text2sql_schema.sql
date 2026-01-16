-- =============================================================================
-- Text2SQL Schema SQL 脚本
--
-- 功能说明:
-- 1. 列敏感度标签表（存储列的敏感级别）
-- 2. 脱敏函数（部分遮蔽、隐藏）
-- 3. Analytics 视图（脱敏后的数据）
-- =============================================================================

-- =============================================================================
-- 第一部分：在 knowledge_lib 数据库中创建列敏感度标签表
-- =============================================================================

USE knowledge_lib;

-- -----------------------------------------------------------------------------
-- 创建列敏感度标签表
-- -----------------------------------------------------------------------------
DROP TABLE IF EXISTS column_sensitivity_tags;

CREATE TABLE column_sensitivity_tags (
    id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    database_name   VARCHAR(100)     NOT NULL COMMENT '数据库名称',
    table_name      VARCHAR(100)     NOT NULL COMMENT '表名',
    column_name     VARCHAR(100)     NOT NULL COMMENT '列名',
    sensitivity_level ENUM('public', 'internal', 'pii', 'sensitive') NOT NULL DEFAULT 'public' COMMENT '敏感级别: public=公开, internal=内部, pii=个人身份信息, sensitive=敏感',
    masking_rule    VARCHAR(50)      DEFAULT NULL COMMENT '脱敏规则: email/phone/name/address/salary等',
    description     TEXT             DEFAULT NULL COMMENT '字段描述',
    created_at      DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at      DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

    UNIQUE KEY uk_column (database_name, table_name, column_name),
    INDEX idx_sensitivity_level (sensitivity_level),
    INDEX idx_database_table (database_name, table_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='列敏感度标签表';

-- =============================================================================
-- 第二部分：在 ecommerce 数据库中创建脱敏函数和 Analytics 视图
-- =============================================================================

USE ecommerce;

-- -----------------------------------------------------------------------------
-- 删除已存在的脱敏函数（如果存在）
-- -----------------------------------------------------------------------------
DROP FUNCTION IF EXISTS mask_column;
DROP FUNCTION IF EXISTS mask_pii;
DROP FUNCTION IF EXISTS mask_sensitive;

-- -----------------------------------------------------------------------------
-- 创建脱敏函数
-- -----------------------------------------------------------------------------
DELIMITER $$

-- 主脱敏函数
CREATE FUNCTION mask_column(value TEXT, level VARCHAR(20)) RETURNS TEXT
DETERMINISTIC
READS SQL DATA
BEGIN
    IF value IS NULL THEN
        RETURN NULL;
    END IF;

    IF level = 'public' OR level = 'internal' THEN
        RETURN value;
    ELSEIF level = 'pii' THEN
        RETURN mask_pii(value);
    ELSEIF level = 'sensitive' THEN
        RETURN mask_sensitive(value);
    ELSE
        RETURN value;
    END IF;
END$$

-- PII 部分遮蔽函数
CREATE FUNCTION mask_pii(value TEXT) RETURNS TEXT
DETERMINISTIC
READS SQL DATA
BEGIN
    DECLARE val_str VARCHAR(1000);
    DECLARE len INT;
    DECLARE head_len INT;
    DECLARE tail_len INT;

    IF value IS NULL THEN
        RETURN NULL;
    END IF;

    SET val_str = TRIM(CAST(value AS CHAR(1000)));
    SET len = CHAR_LENGTH(val_str);

    IF len = 0 THEN
        RETURN '';
    ELSEIF len <= 4 THEN
        RETURN '****';
    ELSEIF len <= 8 THEN
        SET head_len = 2;
        SET tail_len = 2;
    ELSE
        SET head_len = 3;
        SET tail_len = 4;
    END IF;

    RETURN CONCAT(LEFT(val_str, head_len), '****', RIGHT(val_str, tail_len));
END$$

-- 敏感数据遮蔽函数
CREATE FUNCTION mask_sensitive(value TEXT) RETURNS TEXT
DETERMINISTIC
READS SQL DATA
BEGIN
    IF value IS NULL THEN
        RETURN NULL;
    END IF;

    RETURN '[SENSITIVE]';
END$$

DELIMITER ;

-- -----------------------------------------------------------------------------
-- 删除已存在的 Analytics 视图（如果存在）
-- -----------------------------------------------------------------------------
DROP VIEW IF EXISTS v_analytics_users;
DROP VIEW IF EXISTS v_analytics_orders;
DROP VIEW IF EXISTS v_analytics_products;
DROP VIEW IF EXISTS v_analytics_order_items;
DROP VIEW IF EXISTS v_analytics_order_fact;
DROP VIEW IF EXISTS v_analytics_user_summary;
DROP VIEW IF EXISTS v_analytics_product_summary;

-- -----------------------------------------------------------------------------
-- 创建 Analytics 脱敏视图
-- -----------------------------------------------------------------------------

-- 用户表脱敏视图
CREATE VIEW v_analytics_users AS
SELECT
    id,
    name,
    '***@***.***' AS email,  -- 完全脱敏邮箱
    age,
    created_at
FROM users;

-- 订单表脱敏视图（去除 user_id 关联）
CREATE VIEW v_analytics_orders AS
SELECT
    id,
    NULL AS user_id,  -- 隐藏用户关联
    product_name,
    quantity,
    price,
    order_date
FROM orders;

-- 产品表视图（无需脱敏,内部数据）
CREATE VIEW v_analytics_products AS
SELECT
    id,
    name,
    category,
    price,
    stock,
    description
FROM products;

-- 订单项表视图（无需脱敏）
CREATE VIEW v_analytics_order_items AS
SELECT
    oi.id,
    oi.order_id,
    p.name AS product_name,
    oi.quantity,
    oi.unit_price,
    o.order_date
FROM order_items oi
JOIN orders o ON oi.order_id = o.id
JOIN products p ON oi.product_id = p.id;

-- 订单事实表（按日期预聚合）
CREATE VIEW v_analytics_order_fact AS
SELECT
    DATE(order_date) AS order_date,
    COUNT(*) AS order_count,
    SUM(price) AS total_revenue,
    AVG(price) AS avg_order_value,
    SUM(quantity) AS total_quantity,
    COUNT(DISTINCT id) AS unique_orders
FROM orders
GROUP BY DATE(order_date);

-- 用户行为汇总视图
CREATE VIEW v_analytics_user_summary AS
SELECT
    u.id AS user_id,
    u.name,
    COUNT(DISTINCT o.id) AS order_count,
    SUM(o.price) AS total_spent,
    MAX(o.order_date) AS last_order_date,
    DATEDIFF(CURDATE(), MIN(u.created_at)) AS account_age_days
FROM users u
LEFT JOIN orders o ON u.id = o.user_id
GROUP BY u.id;

-- 产品汇总视图
CREATE VIEW v_analytics_product_summary AS
SELECT
    p.id,
    p.name,
    p.category,
    p.price,
    COUNT(DISTINCT oi.order_id) AS order_count,
    SUM(oi.quantity) AS total_sold,
    SUM(oi.quantity * oi.unit_price) AS total_revenue
FROM products p
LEFT JOIN order_items oi ON p.id = oi.product_id
GROUP BY p.id;

-- =============================================================================
-- 脚本完成提示
-- =============================================================================
SELECT 'Text2SQL Schema SQL 脚本执行完成！' AS status;
SELECT '1. 列敏感度标签表已创建' AS step_1;
SELECT '2. 脱敏函数已创建' AS step_2;
SELECT '3. Analytics 视图已创建' AS step_3;
