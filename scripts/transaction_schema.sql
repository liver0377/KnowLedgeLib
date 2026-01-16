USE ecommerce;

DROP TABLE IF EXISTS user_events;
DROP TABLE IF EXISTS order_promotions;
DROP TABLE IF EXISTS promotions;
DROP TABLE IF EXISTS product_suppliers;
DROP TABLE IF EXISTS suppliers;
DROP TABLE IF EXISTS inventory_logs;
DROP TABLE IF EXISTS product_variants;
DROP TABLE IF EXISTS refunds;
DROP TABLE IF EXISTS payments;
DROP TABLE IF EXISTS order_status_history;
DROP TABLE IF EXISTS addresses;
DROP TABLE IF EXISTS regions;

CREATE TABLE regions (
  id INT PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(100) NOT NULL,
  parent_id INT,
  level ENUM('country','province','city','district'),
  FOREIGN KEY (parent_id) REFERENCES regions(id)
);

CREATE TABLE addresses (
  id INT PRIMARY KEY AUTO_INCREMENT,
  user_id INT,
  region_id INT,
  detail VARCHAR(255),
  is_default BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id),
  FOREIGN KEY (region_id) REFERENCES regions(id)
);

CREATE TABLE order_status_history (
  id INT PRIMARY KEY AUTO_INCREMENT,
  order_id INT,
  status ENUM(
    'created','paid','shipped','delivered',
    'cancelled','refunded'
  ),
  changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (order_id) REFERENCES orders(id)
);

CREATE TABLE payments (
  id INT PRIMARY KEY AUTO_INCREMENT,
  order_id INT,
  payment_method ENUM('alipay','wechat','credit_card','paypal'),
  amount DECIMAL(10,2),
  payment_status ENUM('pending','success','failed'),
  paid_at TIMESTAMP,
  FOREIGN KEY (order_id) REFERENCES orders(id)
);

CREATE TABLE refunds (
  id INT PRIMARY KEY AUTO_INCREMENT,
  payment_id INT,
  refund_amount DECIMAL(10,2),
  refund_reason VARCHAR(255),
  refunded_at TIMESTAMP,
  FOREIGN KEY (payment_id) REFERENCES payments(id)
);

CREATE TABLE product_variants (
  id INT PRIMARY KEY AUTO_INCREMENT,
  product_id INT,
  sku_code VARCHAR(100) UNIQUE,
  color VARCHAR(50),
  size VARCHAR(50),
  price DECIMAL(10,2),
  stock INT DEFAULT 0,
  FOREIGN KEY (product_id) REFERENCES products(id)
);

CREATE TABLE inventory_logs (
  id INT PRIMARY KEY AUTO_INCREMENT,
  variant_id INT,
  change_type ENUM('in','out','adjust'),
  quantity INT,
  changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (variant_id) REFERENCES product_variants(id)
);

CREATE TABLE suppliers (
  id INT PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(200),
  contact_email VARCHAR(150)
);

CREATE TABLE product_suppliers (
  product_id INT,
  supplier_id INT,
  PRIMARY KEY (product_id, supplier_id),
  FOREIGN KEY (product_id) REFERENCES products(id),
  FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
);

CREATE TABLE promotions (
  id INT PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(200),
  discount_type ENUM('percentage','fixed'),
  discount_value DECIMAL(10,2),
  start_date DATE,
  end_date DATE
);

CREATE TABLE order_promotions (
  order_id INT,
  promotion_id INT,
  PRIMARY KEY (order_id, promotion_id),
  FOREIGN KEY (order_id) REFERENCES orders(id),
  FOREIGN KEY (promotion_id) REFERENCES promotions(id)
);

CREATE TABLE user_events (
  id INT PRIMARY KEY AUTO_INCREMENT,
  user_id INT,
  event_type ENUM('view','add_to_cart','search','purchase'),
  target VARCHAR(255),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id)
);
