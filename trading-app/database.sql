-- TradeWise Database Schema
-- Create Database
CREATE DATABASE IF NOT EXISTS tradewise_db;
USE tradewise_db;

-- Users Table
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    phone VARCHAR(15),
    balance DECIMAL(15, 2) DEFAULT 10000.00,
    profile_pic VARCHAR(255),
    social_provider VARCHAR(50),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_username (username),
    INDEX idx_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Admins Table
CREATE TABLE IF NOT EXISTS admins (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('super_admin', 'sub_admin') DEFAULT 'sub_admin',
    last_login TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Stocks Table
CREATE TABLE IF NOT EXISTS stocks (
    id INT AUTO_INCREMENT PRIMARY KEY,
    symbol VARCHAR(20) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    current_price DECIMAL(15, 2) NOT NULL,
    change_percent DECIMAL(5, 2) DEFAULT 0.00,
    sector VARCHAR(50),
    category VARCHAR(50),
    market_cap DECIMAL(20, 2),
    volume BIGINT DEFAULT 0,
    pe_ratio DECIMAL(10, 2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_symbol (symbol),
    INDEX idx_sector (sector),
    INDEX idx_category (category)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Holdings Table (User's Stock Portfolio)
CREATE TABLE IF NOT EXISTS holdings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    stock_id INT NOT NULL,
    quantity DECIMAL(15, 4) NOT NULL DEFAULT 0,
    avg_buy_price DECIMAL(15, 2) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (stock_id) REFERENCES stocks(id) ON DELETE CASCADE,
    UNIQUE KEY unique_user_stock (user_id, stock_id),
    INDEX idx_user_id (user_id),
    INDEX idx_stock_id (stock_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Transactions Table
CREATE TABLE IF NOT EXISTS transactions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    stock_id INT NOT NULL,
    transaction_type ENUM('BUY', 'SELL') NOT NULL,
    quantity DECIMAL(15, 4) NOT NULL,
    price_per_unit DECIMAL(15, 2) NOT NULL,
    total_amount DECIMAL(15, 2) NOT NULL,
    brokerage DECIMAL(10, 2) DEFAULT 0.00,
    status ENUM('PENDING', 'APPROVED', 'REJECTED') DEFAULT 'APPROVED',
    transaction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (stock_id) REFERENCES stocks(id) ON DELETE CASCADE,
    INDEX idx_user_id (user_id),
    INDEX idx_stock_id (stock_id),
    INDEX idx_transaction_date (transaction_date),
    INDEX idx_transaction_type (transaction_type),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Fund Requests Table
CREATE TABLE IF NOT EXISTS fund_requests (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    amount DECIMAL(15, 2) NOT NULL,
    type ENUM('DEPOSIT', 'WITHDRAWAL', 'CREDIT', 'DEBIT') NOT NULL,
    reason VARCHAR(255),
    status ENUM('PENDING', 'APPROVED', 'REJECTED') DEFAULT 'PENDING',
    admin_id INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (admin_id) REFERENCES admins(id) ON DELETE SET NULL,
    INDEX idx_user_id (user_id),
    INDEX idx_status (status),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- System Settings Table
CREATE TABLE IF NOT EXISTS system_settings (
    id INT PRIMARY KEY,
    trading_enabled BOOLEAN DEFAULT TRUE,
    brokerage_percent DECIMAL(3, 2) DEFAULT 0.10,
    market_open TIME DEFAULT '09:15:00',
    market_close TIME DEFAULT '15:30:00',
    timezone VARCHAR(50) DEFAULT 'Asia/Kolkata',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Announcements Table
CREATE TABLE IF NOT EXISTS announcements (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    priority ENUM('low', 'normal', 'high', 'urgent') DEFAULT 'normal',
    created_by INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by) REFERENCES admins(id) ON DELETE SET NULL,
    INDEX idx_created_at (created_at),
    INDEX idx_priority (priority)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Insert Default Admin (password: admin123)
INSERT INTO admins (username, password_hash, role) VALUES 
('admin', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.G0dEiZPJZhF0uG', 'super_admin');

-- Insert Default System Settings
INSERT INTO system_settings (id, trading_enabled, brokerage_percent) VALUES 
(1, TRUE, 0.10);

-- Insert Sample Stocks (Indian Market)
INSERT INTO stocks (symbol, name, current_price, sector, category, change_percent) VALUES
('RELIANCE', 'Reliance Industries Ltd', 2450.00, 'Energy', 'energy', 1.25),
('TCS', 'Tata Consultancy Services', 3650.00, 'Technology', 'technology', 0.85),
('HDFCBANK', 'HDFC Bank Ltd', 1620.00, 'Finance', 'finance', -0.45),
('INFY', 'Infosys Ltd', 1480.00, 'Technology', 'technology', 1.10),
('ICICIBANK', 'ICICI Bank Ltd', 980.00, 'Finance', 'finance', 0.65),
('SBIN', 'State Bank of India', 620.00, 'Finance', 'finance', -0.30),
('BHARTIARTL', 'Bharti Airtel Ltd', 1150.00, 'Technology', 'technology', 1.50),
('ITC', 'ITC Ltd', 450.00, 'Consumer', 'consumer', 0.20),
('HINDUNILVR', 'Hindustan Unilever Ltd', 2580.00, 'Consumer', 'consumer', -0.15),
('BAJFINANCE', 'Bajaj Finance Ltd', 6850.00, 'Finance', 'finance', 2.10),
('ASIANPAINT', 'Asian Paints Ltd', 3120.00, 'Consumer', 'consumer', 0.55),
('MARUTI', 'Maruti Suzuki India Ltd', 10250.00, 'Consumer', 'consumer', -0.80),
('TATAMOTORS', 'Tata Motors Ltd', 720.00, 'Consumer', 'consumer', 1.75),
('WIPRO', 'Wipro Ltd', 450.00, 'Technology', 'technology', 0.40),
('NTPC', 'NTPC Ltd', 285.00, 'Energy', 'energy', 0.90),
('POWERGRID', 'Power Grid Corporation', 245.00, 'Energy', 'energy', -0.25),
('TATASTEEL', 'Tata Steel Ltd', 135.00, 'Materials', 'other', 1.35),
('SUNPHARMA', 'Sun Pharmaceutical Industries', 1180.00, 'Healthcare', 'healthcare', 0.70),
('DRREDDY', 'Dr. Reddy''s Laboratories', 5450.00, 'Healthcare', 'healthcare', -0.50),
('CIPLA', 'Cipla Ltd', 1250.00, 'Healthcare', 'healthcare', 0.95);

-- Create Views for Common Queries

-- User Portfolio View
CREATE OR REPLACE VIEW user_portfolio AS
SELECT 
    u.id as user_id,
    u.username,
    u.balance,
    h.stock_id,
    s.symbol,
    s.name as stock_name,
    h.quantity,
    h.avg_buy_price,
    s.current_price,
    (h.quantity * s.current_price) as current_value,
    (h.quantity * h.avg_buy_price) as invested_value,
    ((h.quantity * s.current_price) - (h.quantity * h.avg_buy_price)) as profit_loss,
    (((h.quantity * s.current_price) - (h.quantity * h.avg_buy_price)) / (h.quantity * h.avg_buy_price) * 100) as profit_loss_percent
FROM users u
JOIN holdings h ON u.id = h.user_id
JOIN stocks s ON h.stock_id = s.id;

-- Daily Trading Summary View
CREATE OR REPLACE VIEW daily_trading_summary AS
SELECT 
    DATE(transaction_date) as trade_date,
    transaction_type,
    COUNT(*) as total_trades,
    SUM(quantity) as total_quantity,
    SUM(total_amount) as total_volume,
    AVG(total_amount) as avg_trade_value,
    COUNT(DISTINCT user_id) as active_traders
FROM transactions
GROUP BY DATE(transaction_date), transaction_type
ORDER BY trade_date DESC;

-- Top Traders View
CREATE OR REPLACE VIEW top_traders AS
SELECT 
    u.id,
    u.username,
    u.balance,
    COUNT(t.id) as total_trades,
    SUM(CASE WHEN t.transaction_type = 'BUY' THEN t.total_amount ELSE 0 END) as total_bought,
    SUM(CASE WHEN t.transaction_type = 'SELL' THEN t.total_amount ELSE 0 END) as total_sold,
    (SUM(CASE WHEN t.transaction_type = 'SELL' THEN t.total_amount ELSE 0 END) - 
     SUM(CASE WHEN t.transaction_type = 'BUY' THEN t.total_amount ELSE 0 END)) as net_trading_value
FROM users u
LEFT JOIN transactions t ON u.id = t.user_id
GROUP BY u.id, u.username, u.balance
ORDER BY net_trading_value DESC
LIMIT 10;

-- Create Indexes for Performance
CREATE INDEX idx_holdings_user_stock ON holdings(user_id, stock_id);
CREATE INDEX idx_transactions_user_date ON transactions(user_id, transaction_date);
CREATE INDEX idx_transactions_stock_date ON transactions(stock_id, transaction_date);
CREATE INDEX idx_fund_requests_user_status ON fund_requests(user_id, status);

-- Create Trigger to Update Holdings on Transaction
DELIMITER $$

CREATE TRIGGER after_transaction_insert
AFTER INSERT ON transactions
FOR EACH ROW
BEGIN
    IF NEW.status = 'APPROVED' THEN
        IF NEW.transaction_type = 'BUY' THEN
            -- Insert or update holdings for BUY
            INSERT INTO holdings (user_id, stock_id, quantity, avg_buy_price)
            VALUES (NEW.user_id, NEW.stock_id, NEW.quantity, NEW.price_per_unit)
            ON DUPLICATE KEY UPDATE
                quantity = quantity + NEW.quantity,
                avg_buy_price = ((avg_buy_price * quantity) + (NEW.price_per_unit * NEW.quantity)) / (quantity + NEW.quantity);
        ELSEIF NEW.transaction_type = 'SELL' THEN
            -- Update holdings for SELL
            UPDATE holdings 
            SET quantity = quantity - NEW.quantity
            WHERE user_id = NEW.user_id AND stock_id = NEW.stock_id;
            
            -- Delete holding if quantity is zero or negative
            DELETE FROM holdings 
            WHERE user_id = NEW.user_id AND stock_id = NEW.stock_id AND quantity <= 0;
        END IF;
    END IF;
END$$

DELIMITER ;

-- Create Stored Procedure for User Registration
DELIMITER $$

CREATE PROCEDURE register_user(
    IN p_username VARCHAR(50),
    IN p_email VARCHAR(100),
    IN p_password_hash VARCHAR(255),
    IN p_phone VARCHAR(15),
    IN p_social_provider VARCHAR(50)
)
BEGIN
    DECLARE user_exists INT DEFAULT 0;
    
    SELECT COUNT(*) INTO user_exists 
    FROM users 
    WHERE username = p_username OR email = p_email;
    
    IF user_exists > 0 THEN
        SIGNAL SQLSTATE '45000' 
        SET MESSAGE_TEXT = 'Username or email already exists';
    ELSE
        INSERT INTO users (username, email, password_hash, phone, social_provider)
        VALUES (p_username, p_email, p_password_hash, p_phone, p_social_provider);
        
        SELECT LAST_INSERT_ID() as user_id;
    END IF;
END$$

DELIMITER ;

-- Create Stored Procedure for Execute Trade
DELIMITER $$

CREATE PROCEDURE execute_trade(
    IN p_user_id INT,
    IN p_stock_id INT,
    IN p_transaction_type ENUM('BUY', 'SELL'),
    IN p_quantity DECIMAL(15,4),
    IN p_price_per_unit DECIMAL(15,2),
    IN p_brokerage_percent DECIMAL(3,2)
)
BEGIN
    DECLARE v_current_balance DECIMAL(15,2);
    DECLARE v_total_amount DECIMAL(15,2);
    DECLARE v_brokerage DECIMAL(10,2);
    DECLARE v_holding_quantity DECIMAL(15,4) DEFAULT 0;
    
    -- Calculate total amount and brokerage
    SET v_total_amount = p_quantity * p_price_per_unit;
    SET v_brokerage = v_total_amount * (p_brokerage_percent / 100);
    
    -- Get current balance
    SELECT balance INTO v_current_balance FROM users WHERE id = p_user_id;
    
    IF p_transaction_type = 'BUY' THEN
        -- Check if sufficient balance
        IF v_current_balance >= (v_total_amount + v_brokerage) THEN
            -- Deduct from balance
            UPDATE users SET balance = balance - (v_total_amount + v_brokerage) WHERE id = p_user_id;
            
            -- Insert transaction
            INSERT INTO transactions (user_id, stock_id, transaction_type, quantity, price_per_unit, total_amount, brokerage, status)
            VALUES (p_user_id, p_stock_id, p_transaction_type, p_quantity, p_price_per_unit, v_total_amount, v_brokerage, 'APPROVED');
            
            SELECT 'SUCCESS' as status, 'Buy order executed successfully' as message;
        ELSE
            SELECT 'FAILED' as status, 'Insufficient balance' as message;
        END IF;
        
    ELSEIF p_transaction_type = 'SELL' THEN
        -- Check if sufficient holdings
        SELECT COALESCE(SUM(quantity), 0) INTO v_holding_quantity 
        FROM holdings 
        WHERE user_id = p_user_id AND stock_id = p_stock_id;
        
        IF v_holding_quantity >= p_quantity THEN
            -- Add to balance
            UPDATE users SET balance = balance + (v_total_amount - v_brokerage) WHERE id = p_user_id;
            
            -- Insert transaction
            INSERT INTO transactions (user_id, stock_id, transaction_type, quantity, price_per_unit, total_amount, brokerage, status)
            VALUES (p_user_id, p_stock_id, p_transaction_type, p_quantity, p_price_per_unit, v_total_amount, v_brokerage, 'APPROVED');
            
            SELECT 'SUCCESS' as status, 'Sell order executed successfully' as message;
        ELSE
            SELECT 'FAILED' as status, 'Insufficient holdings' as message;
        END IF;
    END IF;
END$$

DELIMITER ;

-- Grant Privileges (Optional - adjust as needed)
-- GRANT ALL PRIVILEGES ON tradewise_db.* TO 'tradewise_user'@'localhost' IDENTIFIED BY 'your_password';
-- FLUSH PRIVILEGES;

-- Display Summary
SELECT 'Database schema created successfully!' as Status;
SELECT COUNT(*) as total_users FROM users;
SELECT COUNT(*) as total_admins FROM admins;
SELECT COUNT(*) as total_stocks FROM stocks;
SELECT COUNT(*) as total_holdings FROM holdings;
SELECT COUNT(*) as total_transactions FROM transactions;