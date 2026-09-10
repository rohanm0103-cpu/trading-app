# add_stocks.py
import mysql.connector
from mysql.connector import Error

stocks = [
    ('AAPL', 'Apple Inc.', 178.50),
    ('MSFT', 'Microsoft Corporation', 415.60),
    ('GOOGL', 'Alphabet Inc. Class A', 141.80),
    ('AMZN', 'Amazon.com Inc.', 178.25),
    ('META', 'Meta Platforms Inc.', 493.50),
    ('NVDA', 'NVIDIA Corporation', 875.30),
    ('AMD', 'Advanced Micro Devices Inc.', 178.90),
    ('INTC', 'Intel Corporation', 32.45),
    ('CRM', 'Salesforce Inc.', 285.70),
    ('ADBE', 'Adobe Inc.', 565.20),
    ('NFLX', 'Netflix Inc.', 628.40),
    ('TSLA', 'Tesla Inc.', 248.30),
    ('RIVN', 'Rivian Automotive Inc.', 11.25),
    ('LCID', 'Lucid Group Inc.', 3.15),
    ('NIO', 'NIO Inc. ADR', 5.85),
    ('COIN', 'Coinbase Global Inc.', 245.80),
    ('MSTR', 'MicroStrategy Incorporated', 1425.60),
    ('RIOT', 'Riot Platforms Inc.', 12.35),
    ('MARA', 'Marathon Digital Holdings Inc.', 18.90),
    ('GME', 'GameStop Corp.', 18.75),
    ('AMC', 'AMC Entertainment Holdings Inc.', 4.25),
    ('PLTR', 'Palantir Technologies Inc.', 24.60),
    ('SOFI', 'SoFi Technologies Inc.', 7.85),
    ('SPY', 'SPDR S&P 500 ETF Trust', 512.30),
    ('QQQ', 'Invesco QQQ Trust', 445.80),
    ('NFTY', 'First Trust India NIFTY 50 Equal Weight ETF', 214.65),
]

try:
    conn = mysql.connector.connect(
        host='127.0.0.1',
        user='root',
        password='',
        database='trading_app'
    )
    
    if conn.is_connected():
        cursor = conn.cursor()
        
        for symbol, name, price in stocks:
            cursor.execute("""
                INSERT INTO stocks (symbol, name, current_price) 
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE 
                    name = VALUES(name),
                    current_price = VALUES(current_price)
            """, (symbol, name, price))
        
        conn.commit()
        print(f"✅ Successfully added {len(stocks)} stocks!")
        
        cursor.close()
        conn.close()
        
except Error as e:
    print(f"❌ Error: {e}")
