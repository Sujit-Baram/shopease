-- ShopEase sample products (the API adds these automatically when the table is empty).

INSERT IGNORE INTO products (id, name, category, description, price, stock, emoji) VALUES
  (1, 'Wireless Earbuds', 'Electronics', 'Bluetooth 5.3 earbuds with noise cancelling and 30-hour battery.', 2499, 25, '🎧'),
  (2, 'Smart Watch', 'Electronics', 'Heart rate, steps and sleep tracking with a 7-day battery.', 4999, 15, '⌚'),
  (3, 'Laptop 14-inch', 'Electronics', 'Thin and light laptop: 16 GB RAM, 512 GB SSD, full HD screen.', 45000, 8, '💻'),
  (4, 'Bluetooth Speaker', 'Electronics', 'Waterproof portable speaker with deep bass.', 1999, 30, '🔊'),
  (5, 'Power Bank 20000mAh', 'Electronics', 'Fast-charging power bank with two USB ports.', 1299, 3, '🔋'),
  (6, 'Running Shoes', 'Fashion', 'Lightweight running shoes with cushioned soles.', 2999, 20, '👟'),
  (7, 'Denim Jacket', 'Fashion', 'Classic blue denim jacket, regular fit.', 1799, 12, '🧥'),
  (8, 'Sunglasses', 'Fashion', 'UV400 polarised sunglasses with a hard case.', 899, 40, '🕶️'),
  (9, 'Travel Backpack', 'Fashion', '30-litre backpack with a padded laptop pocket.', 1499, 18, '🎒'),
  (10, 'Coffee Mug Set', 'Home', 'Set of 4 ceramic mugs, microwave safe.', 599, 35, '☕'),
  (11, 'Table Lamp', 'Home', 'LED desk lamp with 3 brightness levels.', 1099, 0, '💡'),
  (12, 'Indoor Plant', 'Home', 'Easy-care money plant in a ceramic pot.', 449, 22, '🪴');

-- A database user for the app (run as the RDS admin user, then put these values in shopease.env):
-- CREATE USER 'shopease'@'%' IDENTIFIED BY 'choose-a-strong-password';
-- GRANT ALL PRIVILEGES ON shopease.* TO 'shopease'@'%';   -- only on the shopease database (the API creates its own tables)
