-- ShopEase tables for MySQL / Amazon RDS for MySQL (Module 4).
-- The API also creates these automatically on start; this file is for running by hand:
--   mysql -h <rds-endpoint> -u admin -p shopease < database/schema.mysql.sql

CREATE TABLE IF NOT EXISTS products (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(120) NOT NULL,
        category VARCHAR(60) NOT NULL,
        description TEXT NOT NULL,
        price INT NOT NULL,
        stock INT NOT NULL DEFAULT 0,
        emoji VARCHAR(16) NOT NULL DEFAULT '',
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    ) CHARACTER SET utf8mb4;

CREATE TABLE IF NOT EXISTS orders (
        id INT AUTO_INCREMENT PRIMARY KEY,
        customer_name VARCHAR(120) NOT NULL,
        email VARCHAR(160) NOT NULL,
        phone VARCHAR(20) NOT NULL,
        address VARCHAR(400) NOT NULL,
        total INT NOT NULL,
        status VARCHAR(20) NOT NULL DEFAULT 'PLACED',
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    ) CHARACTER SET utf8mb4;

CREATE TABLE IF NOT EXISTS order_items (
        id INT AUTO_INCREMENT PRIMARY KEY,
        order_id INT NOT NULL,
        product_id INT NOT NULL,
        product_name VARCHAR(120) NOT NULL,
        unit_price INT NOT NULL,
        qty INT NOT NULL,
        FOREIGN KEY (order_id) REFERENCES orders(id),
        FOREIGN KEY (product_id) REFERENCES products(id)
    ) CHARACTER SET utf8mb4;

