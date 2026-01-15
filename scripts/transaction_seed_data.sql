-- transaction_seed_data.sql
USE ecommerce;

-- 0. 基础数字表（1 ~ 300）
-- 1. 用户
-- 2. 地区 & 地址
-- 3. 商品 / SKU / 供应商
-- 4. 订单 / 订单项
-- 5. 订单状态历史
-- 6. 支付 & 退款
-- 7. 优惠
-- 8. 用户行为


WITH RECURSIVE seq AS (
  SELECT 1 AS n
  UNION ALL
  SELECT n + 1 FROM seq WHERE n < 300
)
SELECT * FROM seq;

INSERT INTO users (name, email, age)
SELECT
  CONCAT('User_', n),
  CONCAT('user', n, '@example.com'),
  18 + (n % 40)
FROM (
  WITH RECURSIVE seq AS (
    SELECT 1 n UNION ALL SELECT n+1 FROM seq WHERE n < 300
  ) SELECT n FROM seq
) t;

INSERT INTO regions (name, parent_id, level) VALUES
('China', NULL, 'country'),
('Beijing', 1, 'province'),
('Shanghai', 1, 'province'),
('Guangdong', 1, 'province'),
('Beijing City', 2, 'city'),
('Shanghai City', 3, 'city'),
('Guangzhou', 4, 'city'),
('Shenzhen', 4, 'city');

INSERT INTO addresses (user_id, region_id, detail, is_default)
SELECT
  u.id,
  5 + (u.id % 4),
  CONCAT('Street ', u.id),
  TRUE
FROM users u;

INSERT INTO addresses (user_id, region_id, detail, is_default)
SELECT
  u.id,
  5 + ((u.id + 1) % 4),
  CONCAT('Backup Street ', u.id),
  FALSE
FROM users u
WHERE u.id % 3 = 0;

INSERT INTO products (name, category, price, stock)
SELECT
  CONCAT('Product_', n),
  CASE WHEN n % 3 = 0 THEN 'Electronics'
       WHEN n % 3 = 1 THEN 'Clothing'
       ELSE 'Home' END,
  50 + (n % 200),
  100
FROM (
  WITH RECURSIVE seq AS (
    SELECT 1 n UNION ALL SELECT n+1 FROM seq WHERE n <= 30
  ) SELECT n FROM seq
) t;

INSERT INTO product_variants (product_id, sku_code, color, size, price, stock)
SELECT
  p.id,
  CONCAT('SKU-', p.id, '-', v),
  CASE v WHEN 1 THEN 'Red' ELSE 'Blue' END,
  CASE v WHEN 1 THEN 'M' ELSE 'L' END,
  p.price + (v * 10),
  50
FROM products p
JOIN (SELECT 1 v UNION SELECT 2) s;

INSERT INTO orders (user_id, product_name, quantity, price, order_date)
SELECT
  u.id,
  'Mixed Order',
  1,
  100 + (u.id % 200),
  NOW() - INTERVAL (u.id % 60) DAY
FROM users u
WHERE u.id % 2 = 0;

INSERT INTO order_items (order_id, product_id, quantity, unit_price)
SELECT
  o.id,
  p.id,
  1 + (o.id % 3),
  p.price
FROM orders o
JOIN products p ON p.id = (o.id % 30) + 1;

INSERT INTO order_status_history (order_id, status, changed_at)
SELECT id, 'created', order_date FROM orders;

INSERT INTO order_status_history (order_id, status, changed_at)
SELECT id, 'paid', order_date + INTERVAL 1 HOUR FROM orders;

INSERT INTO order_status_history (order_id, status, changed_at)
SELECT id, 'cancelled', order_date + INTERVAL 2 DAY
FROM orders
WHERE id % 10 = 0;

INSERT INTO payments (order_id, payment_method, amount, payment_status, paid_at)
SELECT
  id,
  CASE WHEN id % 2 = 0 THEN 'alipay' ELSE 'wechat' END,
  price,
  'success',
  order_date + INTERVAL 1 HOUR
FROM orders;

INSERT INTO refunds (payment_id, refund_amount, refund_reason, refunded_at)
SELECT
  p.id,
  p.amount,
  'User request',
  p.paid_at + INTERVAL 3 DAY
FROM payments p
WHERE p.id % 15 = 0;

INSERT INTO promotions (name, discount_type, discount_value, start_date, end_date)
VALUES
('Spring Sale', 'percentage', 10, '2024-03-01', '2024-04-01'),
('VIP Coupon', 'fixed', 20, '2024-01-01', '2024-12-31');

INSERT INTO order_promotions (order_id, promotion_id)
SELECT id, 1 FROM orders WHERE id % 4 = 0;

INSERT INTO user_events (user_id, event_type, target, created_at)
SELECT
  u.id,
  CASE WHEN u.id % 4 = 0 THEN 'view'
       WHEN u.id % 4 = 1 THEN 'add_to_cart'
       WHEN u.id % 4 = 2 THEN 'search'
       ELSE 'purchase' END,
  CONCAT('Product_', u.id % 30),
  NOW() - INTERVAL (u.id % 30) DAY
FROM users u;
