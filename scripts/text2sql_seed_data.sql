-- =============================================================================
-- Text2SQL Seed Data SQL 脚本
--
-- 功能说明:
-- 插入列敏感度标签数据到 column_sensitivity_tags 表
--
-- 依赖: 需要先执行 scripts/text2sql_schema.sql 创建 column_sensitivity_tags 表
-- =============================================================================

USE knowledge_lib;

-- -----------------------------------------------------------------------------
-- 插入 ecommerce 数据库的列敏感度标签
-- -----------------------------------------------------------------------------
INSERT INTO column_sensitivity_tags (database_name, table_name, column_name, sensitivity_level, masking_rule, description) VALUES
-- users 表
('ecommerce', 'users', 'name', 'pii', 'name', '用户姓名'),
('ecommerce', 'users', 'email', 'pii', 'email', '用户邮箱'),
('ecommerce', 'users', 'age', 'internal', NULL, '用户年龄'),

-- orders 表
('ecommerce', 'orders', 'user_id', 'internal', NULL, '用户ID'),
('ecommerce', 'orders', 'product_name', 'public', NULL, '产品名称'),
('ecommerce', 'orders', 'quantity', 'public', NULL, '数量'),
('ecommerce', 'orders', 'price', 'internal', NULL, '订单金额'),
('ecommerce', 'orders', 'order_date', 'public', NULL, '订单日期'),

-- products 表
('ecommerce', 'products', 'name', 'public', NULL, '产品名称'),
('ecommerce', 'products', 'category', 'public', NULL, '产品分类'),
('ecommerce', 'products', 'price', 'public', NULL, '产品价格'),
('ecommerce', 'products', 'stock', 'internal', NULL, '库存数量'),
('ecommerce', 'products', 'description', 'public', NULL, '产品描述'),

-- addresses 表（如果存在）
('ecommerce', 'addresses', 'user_id', 'internal', NULL, '用户ID'),
('ecommerce', 'addresses', 'detail', 'pii', 'address', '详细地址'),

-- payments 表（如果存在）
('ecommerce', 'payments', 'order_id', 'internal', NULL, '订单ID'),
('ecommerce', 'payments', 'amount', 'sensitive', 'salary', '支付金额'),
('ecommerce', 'payments', 'payment_method', 'internal', NULL, '支付方式'),

-- user_events 表（如果存在）
('ecommerce', 'user_events', 'user_id', 'internal', NULL, '用户ID'),
('ecommerce', 'user_events', 'event_type', 'public', NULL, '事件类型'),
('ecommerce', 'user_events', 'target', 'internal', NULL, '目标对象')
ON DUPLICATE KEY UPDATE sensitivity_level=VALUES(sensitivity_level);

-- -----------------------------------------------------------------------------
-- analytics 视图列标签（视图中的列无需脱敏）
-- -----------------------------------------------------------------------------
INSERT INTO column_sensitivity_tags (database_name, table_name, column_name, sensitivity_level, masking_rule, description) VALUES
('ecommerce', 'v_analytics_users', 'id', 'public', NULL, '用户ID'),
('ecommerce', 'v_analytics_users', 'name', 'public', NULL, '用户名称'),
('ecommerce', 'v_analytics_users', 'email', 'public', NULL, '邮箱（已脱敏）'),
('ecommerce', 'v_analytics_users', 'age', 'public', NULL, '年龄'),
('ecommerce', 'v_analytics_users', 'created_at', 'public', NULL, '创建时间'),

('ecommerce', 'v_analytics_orders', 'id', 'public', NULL, '订单ID'),
('ecommerce', 'v_analytics_orders', 'user_id', 'public', NULL, '用户ID（已隐藏）'),
('ecommerce', 'v_analytics_orders', 'product_name', 'public', NULL, '产品名称'),
('ecommerce', 'v_analytics_orders', 'quantity', 'public', NULL, '数量'),
('ecommerce', 'v_analytics_orders', 'price', 'public', NULL, '订单金额'),
('ecommerce', 'v_analytics_orders', 'order_date', 'public', NULL, '订单日期'),

('ecommerce', 'v_analytics_order_fact', 'order_date', 'public', NULL, '订单日期'),
('ecommerce', 'v_analytics_order_fact', 'order_count', 'public', NULL, '订单数量'),
('ecommerce', 'v_analytics_order_fact', 'total_revenue', 'public', NULL, '总营收'),
('ecommerce', 'v_analytics_order_fact', 'avg_order_value', 'public', NULL, '平均订单金额'),
('ecommerce', 'v_analytics_order_fact', 'total_quantity', 'public', NULL, '总数量'),
('ecommerce', 'v_analytics_order_fact', 'unique_orders', 'public', NULL, '独立订单数')
ON DUPLICATE KEY UPDATE sensitivity_level=VALUES(sensitivity_level);

-- =============================================================================
-- 验证数据插入结果
-- =============================================================================
SELECT '--- 原始表列敏感度标签 ---' AS info;
SELECT database_name, table_name, column_name, sensitivity_level, description
FROM column_sensitivity_tags
WHERE table_name NOT LIKE 'v_analytics_%'
ORDER BY database_name, table_name, column_name
LIMIT 20;

SELECT '--- Analytics 视图列敏感度标签 ---' AS info;
SELECT database_name, table_name, column_name, sensitivity_level, description
FROM column_sensitivity_tags
WHERE table_name LIKE 'v_analytics_%'
ORDER BY database_name, table_name, column_name;

-- =============================================================================
-- 脚本完成提示
-- =============================================================================
SELECT 'Text2SQL Seed Data SQL 脚本执行完成！' AS status;
SELECT '1. 原始表列敏感度标签已插入' AS step_1;
SELECT '2. Analytics 视图列敏感度标签已插入' AS step_2;
