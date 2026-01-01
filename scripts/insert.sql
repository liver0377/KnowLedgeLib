USE ecommerce;

-- Clean existing data (optional)
SET FOREIGN_KEY_CHECKS = 0;
TRUNCATE TABLE order_items;
TRUNCATE TABLE orders;
TRUNCATE TABLE products;
TRUNCATE TABLE categories;
TRUNCATE TABLE users;
SET FOREIGN_KEY_CHECKS = 1;

-- Categories
INSERT INTO categories (name, description) VALUES
('Electronics', 'Devices, gadgets, and accessories'),
('Home', 'Home improvement and household goods'),
('Books', 'Books and printed media'),
('Fashion', 'Clothing, shoes, and accessories'),
('Sports', 'Sports equipment and outdoor gear');

-- Products
INSERT INTO products (name, category, price, stock, description) VALUES
('Wireless Earbuds', 'Electronics', 199.99, 120, 'Bluetooth noise-cancelling earbuds'),
('USB-C Charger 65W', 'Electronics', 39.90, 300, 'Fast charger with USB-C PD'),
('Smart LED Bulb', 'Home', 15.99, 500, 'Dimmable smart bulb with app control'),
('Stainless Steel Pan', 'Home', 49.50, 80, '10-inch stainless steel frying pan'),
('Modern SQL Guide', 'Books', 29.99, 200, 'Practical SQL patterns and examples'),
('Clean Architecture', 'Books', 34.99, 150, 'Software architecture principles'),
('Running Shoes', 'Fashion', 89.00, 60, 'Lightweight daily running shoes'),
('Denim Jacket', 'Fashion', 79.99, 45, 'Classic denim jacket'),
('Yoga Mat', 'Sports', 25.00, 110, 'Non-slip yoga mat'),
('Camping Lantern', 'Sports', 19.99, 140, 'Rechargeable LED lantern');

-- Users
INSERT INTO users (name, email, age) VALUES
('张三', 'zhangsan@example.com', 28),
('李四', 'lisi@example.com', 34),
('王五', 'wangwu@example.com', 22),
('赵六', 'zhaoliu@example.com', 41),
('钱七', 'qianqi@example.com', 30),
('孙八', 'sunba@example.com', 26),
('周九', 'zhoujiu@example.com', 37),
('吴十', 'wushi@example.com', 24);

-- Orders
INSERT INTO orders (user_id, product_name, quantity, price, order_date) VALUES
(1, 'Wireless Earbuds', 1, 199.99, '2025-12-12 10:15:00'),
(1, 'USB-C Charger 65W', 2, 39.90,  '2025-12-15 14:20:00'),
(2, 'Stainless Steel Pan', 1, 49.50, '2025-12-10 09:05:00'),
(2, 'Smart LED Bulb', 4, 15.99,     '2025-12-18 19:30:00'),
(3, 'Modern SQL Guide', 1, 29.99,    '2025-12-20 11:00:00'),
(4, 'Running Shoes', 1, 89.00,       '2025-12-05 08:45:00'),
(5, 'Yoga Mat', 2, 25.00,            '2025-12-22 16:10:00'),
(6, 'Camping Lantern', 3, 19.99,     '2025-12-23 20:40:00'),
(7, 'Denim Jacket', 1, 79.99,        '2025-12-24 13:25:00'),
(8, 'Clean Architecture', 1, 34.99,  '2025-12-25 09:55:00');

-- Order Items (linking orders to products)
-- Note: orders.id is AUTO_INCREMENT, assuming IDs 1..10 in insertion order above.
INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES
(1, 1, 1, 199.99),
(2, 2, 2, 39.90),
(3, 4, 1, 49.50),
(4, 3, 4, 15.99),
(5, 5, 1, 29.99),
(6, 7, 1, 89.00),
(7, 9, 2, 25.00),
(8, 10, 3, 19.99),
(9, 8, 1, 79.99),
(10, 6, 1, 34.99);

-- Optional: a few more order_items per order to make joins more interesting
INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES
(1, 2, 1, 39.90),
(3, 3, 2, 15.99),
(5, 2, 1, 39.90),
(7, 3, 2, 15.99),
(9, 1, 1, 199.99);

-- Optional: Update orders.price to reflect per-item price if you treat orders.price as unit price.
-- If you want orders.price to represent order total, you can compute it from order_items instead.
