from flask import Flask, render_template, request, jsonify, session, redirect, url_for, Response, make_response
from flask_cors import CORS
import mysql.connector
from mysql.connector import Error
from werkzeug.security import generate_password_hash, check_password_hash
from config import Config
import random
import os
import time
import datetime
import csv
import io
import json
import re
import urllib.parse
import urllib.request
from functools import wraps
from zoneinfo import ZoneInfo

# ============= FLASK APP INITIALIZATION =============
app = Flask(__name__)
CORS(app)
app.config.from_object(Config)
app.secret_key = Config.SECRET_KEY
APP_TIMEZONE = ZoneInfo("Asia/Kolkata")
DEFAULT_STOCKS = [
    ("AAPL", "Apple Inc.", 178.50),
    ("MSFT", "Microsoft Corporation", 415.60),
    ("GOOGL", "Alphabet Inc. Class A", 141.80),
    ("AMZN", "Amazon.com Inc.", 178.25),
    ("META", "Meta Platforms Inc.", 503.40),
    ("RELIANCE", "Reliance Industries Ltd.", 2965.40),
    ("TCS", "Tata Consultancy Services Ltd.", 4128.60),
    ("INFY", "Infosys Ltd.", 1587.45),
    ("HDFCBANK", "HDFC Bank Ltd.", 1681.20),
    ("ICICIBANK", "ICICI Bank Ltd.", 1216.85),
    ("SBIN", "State Bank of India", 812.65),
    ("ITC", "ITC Ltd.", 428.15),
    ("BHARTIARTL", "Bharti Airtel Ltd.", 1294.70),
    ("TATAMOTORS", "Tata Motors Ltd.", 1042.80),
    ("ASIANPAINT", "Asian Paints Ltd.", 2895.55),
    ("NIFTY50", "NIFTY 50", 22350.00),
    ("NVDA", "NVIDIA Corporation", 875.30),
    ("AMD", "Advanced Micro Devices Inc.", 178.90),
    ("INTC", "Intel Corporation", 32.45),
    ("CRM", "Salesforce Inc.", 285.70),
    ("ADBE", "Adobe Inc.", 565.20),
    ("ORCL", "Oracle Corporation", 128.45),
    ("JPM", "JPMorgan Chase & Co.", 198.35),
    ("WMT", "Walmart Inc.", 68.20),
    ("SUNPHARMA", "Sun Pharmaceutical Industries Ltd.", 1628.75),
    ("NFLX", "Netflix Inc.", 628.40),
    ("TSLA", "Tesla Inc.", 248.30),
    ("RIVN", "Rivian Automotive Inc.", 11.25),
    ("LCID", "Lucid Group Inc.", 3.15),
    ("NIO", "NIO Inc. ADR", 5.85),
    ("COIN", "Coinbase Global Inc.", 245.80),
    ("MSTR", "MicroStrategy Incorporated", 1425.60),
    ("RIOT", "Riot Platforms Inc.", 12.35),
    ("MARA", "Marathon Digital Holdings Inc.", 18.90),
    ("GME", "GameStop Corp.", 18.75),
    ("AMC", "AMC Entertainment Holdings Inc.", 4.25),
    ("PLTR", "Palantir Technologies Inc.", 24.60),
    ("SOFI", "SoFi Technologies Inc.", 7.85),
    ("SPY", "SPDR S&P 500 ETF Trust", 512.30),
    ("QQQ", "Invesco QQQ Trust", 445.80),
]
LIVE_QUOTE_CACHE = {
    'fetched_at': 0,
    'quotes': {},
}
LIVE_QUOTE_TTL_SECONDS = 12
USD_TO_INR_RATE = 83.0
YAHOO_SYMBOL_OVERRIDES = {
    'NIFTY50': '^NSEI',
    'RELIANCE': 'RELIANCE.NS',
    'TCS': 'TCS.NS',
    'INFY': 'INFY.NS',
    'HDFCBANK': 'HDFCBANK.NS',
    'ICICIBANK': 'ICICIBANK.NS',
    'SBIN': 'SBIN.NS',
    'ITC': 'ITC.NS',
    'BHARTIARTL': 'BHARTIARTL.NS',
    'TATAMOTORS': 'TATAMOTORS.NS',
    'ASIANPAINT': 'ASIANPAINT.NS',
    'SUNPHARMA': 'SUNPHARMA.NS',
}


def current_local_time():
    """Return timezone-aware current time for app-generated timestamps."""
    return datetime.datetime.now(APP_TIMEZONE)


def apply_live_market_pricing(stocks):
    """Apply deterministic short-interval price movement for UI live refreshes."""
    tick_bucket = int(time.time() // 5)
    enriched = []
    for stock in stocks:
        stock_copy = dict(stock)
        base_price = float(stock_copy.get('current_price') or 0)
        rng = random.Random(f"{stock_copy.get('symbol', 'UNKNOWN')}-{tick_bucket}")
        volatility = 0.008
        if stock_copy.get('symbol') in {'NIFTY50', 'SBIN', 'ITC', 'HDFCBANK', 'ICICIBANK'}:
            volatility = 0.004
        elif stock_copy.get('symbol') in {'AMC', 'GME', 'PLTR', 'SOFI', 'RIVN', 'LCID', 'NIO', 'COIN', 'MSTR', 'RIOT', 'MARA'}:
            volatility = 0.015

        fluctuation = rng.uniform(-volatility, volatility)
        if abs(fluctuation) < 0.0005:
            fluctuation = 0.0005 if rng.random() > 0.5 else -0.0005

        live_price = max(0.01, base_price * (1 + fluctuation))
        stock_copy['current_price'] = round(live_price, 2)
        stock_copy['change_percent'] = round(fluctuation * 100, 2)
        stock_copy['change_amount'] = round(base_price * fluctuation, 2)
        stock_copy['day_high'] = round(live_price * 1.02, 2)
        stock_copy['day_low'] = round(live_price * 0.98, 2)
        enriched.append(stock_copy)
    return enriched


def yahoo_symbol_for_stock(symbol):
    """Map local stock symbols to Yahoo Finance quote symbols."""
    normalized = str(symbol or '').upper()
    return YAHOO_SYMBOL_OVERRIDES.get(normalized, normalized)


def fetch_yahoo_quotes(symbols):
    """Fetch live quotes from Yahoo Finance and cache briefly for UI polling."""
    now = time.time()
    cached_quotes = LIVE_QUOTE_CACHE.get('quotes') or {}
    requested_symbols = [str(symbol or '').upper() for symbol in symbols if symbol]

    if cached_quotes and now - LIVE_QUOTE_CACHE.get('fetched_at', 0) < LIVE_QUOTE_TTL_SECONDS:
        return cached_quotes

    yahoo_to_local = {
        yahoo_symbol_for_stock(symbol): symbol
        for symbol in requested_symbols
    }
    if not yahoo_to_local:
        return {}

    query = urllib.parse.urlencode({'symbols': ','.join(yahoo_to_local.keys())})
    url = f"https://query1.finance.yahoo.com/v7/finance/quote?{query}"
    request_obj = urllib.request.Request(
        url,
        headers={
            'User-Agent': 'Mozilla/5.0 TradeWise market quote refresh',
            'Accept': 'application/json',
        },
    )

    try:
        with urllib.request.urlopen(request_obj, timeout=6) as response:
            payload = json.loads(response.read().decode('utf-8'))
    except Exception as exc:
        print(f"Live quote fetch failed: {exc}")
        return cached_quotes

    quotes = {}
    for item in payload.get('quoteResponse', {}).get('result', []):
        yahoo_symbol = item.get('symbol')
        local_symbol = yahoo_to_local.get(yahoo_symbol)
        price = item.get('regularMarketPrice')
        if not local_symbol or price is None:
            continue

        currency = item.get('currency') or 'INR'
        multiplier = USD_TO_INR_RATE if currency == 'USD' else 1
        change_amount = item.get('regularMarketChange') or 0

        quotes[local_symbol] = {
            'symbol': local_symbol,
            'name': item.get('longName') or item.get('shortName') or local_symbol,
            'current_price': round(float(price) * multiplier, 2),
            'change_percent': round(float(item.get('regularMarketChangePercent') or 0), 2),
            'change_amount': round(float(change_amount) * multiplier, 2),
            'day_high': round(float(item.get('regularMarketDayHigh') or price) * multiplier, 2),
            'day_low': round(float(item.get('regularMarketDayLow') or price) * multiplier, 2),
            'market_cap': round(float(item.get('marketCap') or 0) * multiplier, 2),
            'currency': 'INR',
            'data_source': 'Yahoo Finance',
        }

    if quotes:
        LIVE_QUOTE_CACHE['fetched_at'] = now
        LIVE_QUOTE_CACHE['quotes'] = quotes

    return quotes


def apply_external_market_quotes(stocks):
    """Overlay real market quotes on DB stocks, with simulated movement as fallback."""
    simulated_stocks = apply_live_market_pricing(stocks)
    quotes = fetch_yahoo_quotes([stock.get('symbol') for stock in simulated_stocks])
    if not quotes:
        return simulated_stocks

    enriched = []
    for stock in simulated_stocks:
        stock_copy = dict(stock)
        quote = quotes.get(str(stock_copy.get('symbol') or '').upper())
        if quote:
            stock_copy.update({
                key: value
                for key, value in quote.items()
                if value not in (None, '')
            })
        enriched.append(stock_copy)
    return enriched


def fetch_live_stocks_from_db(symbols=None):
    """Read stocks from the database and return the live UI payload."""
    ensure_default_stocks()
    ensure_stock_management_schema()
    conn = get_db_connection()
    if not conn:
        return None

    cursor = conn.cursor(dictionary=True)
    try:
        base_query = """
            SELECT id, symbol, name, current_price, market_cap, sector, category,
                   COALESCE(change_percent, 0) AS change_percent, last_updated
            FROM stocks
        """
        params = ()
        if symbols:
            placeholders = ', '.join(['%s'] * len(symbols))
            base_query += f" WHERE symbol IN ({placeholders})"
            params = tuple(symbols)
        base_query += " ORDER BY symbol"
        cursor.execute(base_query, params)
        return apply_external_market_quotes(cursor.fetchall())
    finally:
        cursor.close()
        conn.close()


def ensure_default_stocks():
    """Seed baseline stocks so new environments always have tradable symbols."""
    conn = get_db_connection()
    if not conn:
        return

    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM stocks WHERE symbol = %s", ("NFTY",))
        for symbol, name, price in DEFAULT_STOCKS:
            cursor.execute(
                """
                INSERT INTO stocks (symbol, name, current_price)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    name = VALUES(name),
                    current_price = VALUES(current_price)
                """,
                (symbol, name, price),
            )
        conn.commit()
    except Error as e:
        conn.rollback()
        print(f"Default stock seed error: {e}")
    finally:
        cursor.close()
        conn.close()


def ensure_stock_management_schema():
    """Ensure stock admin fields and market settings exist."""
    conn = get_db_connection()
    if not conn:
        return

    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE stocks ADD COLUMN IF NOT EXISTS market_cap DECIMAL(20, 2) DEFAULT 0.00")
        cursor.execute("ALTER TABLE stocks ADD COLUMN IF NOT EXISTS sector VARCHAR(100) DEFAULT ''")
        cursor.execute("ALTER TABLE stocks ADD COLUMN IF NOT EXISTS category VARCHAR(100) DEFAULT ''")
        cursor.execute("ALTER TABLE stocks ADD COLUMN IF NOT EXISTS change_percent DECIMAL(10, 2) DEFAULT 0.00")
        cursor.execute("ALTER TABLE stocks ADD COLUMN IF NOT EXISTS last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS market_settings (
                id INT PRIMARY KEY,
                market_open TIME DEFAULT '09:15:00',
                market_close TIME DEFAULT '15:30:00',
                timezone VARCHAR(64) DEFAULT 'Asia/Kolkata',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            INSERT INTO market_settings (id, market_open, market_close, timezone)
            VALUES (1, '09:15:00', '15:30:00', 'Asia/Kolkata')
            ON DUPLICATE KEY UPDATE id = id
        """)
        conn.commit()
    except Error as e:
        conn.rollback()
        print(f"Stock management schema error: {e}")
    finally:
        cursor.close()
        conn.close()


def ensure_user_schema():
    """Ensure user account fields used by auth/profile pages exist."""
    conn = get_db_connection()
    if not conn:
        return False

    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS phone VARCHAR(15)")
        cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS profile_pic VARCHAR(255)")
        cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS social_provider VARCHAR(50)")
        cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE")
        cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP")
        conn.commit()
        return True
    except Error as e:
        conn.rollback()
        print(f"User schema error: {e}")
        return False
    finally:
        cursor.close()
        conn.close()


def get_market_settings_data():
    """Return persisted market settings with safe defaults."""
    ensure_stock_management_schema()

    def normalize_time_value(value, fallback):
        if not value:
            return fallback
        raw = str(value).strip()
        for fmt in ('%H:%M:%S', '%H:%M', '%I:%M %p', '%I:%M:%S %p'):
            try:
                return datetime.datetime.strptime(raw, fmt).strftime('%H:%M')
            except ValueError:
                continue
        return fallback

    defaults = {
        'market_open': '09:15',
        'market_close': '15:30',
        'timezone': 'Asia/Kolkata',
    }
    conn = get_db_connection()
    if not conn:
        return defaults

    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT market_open, market_close, timezone FROM market_settings WHERE id = 1")
        row = cursor.fetchone()
        if not row:
            return defaults
        return {
            'market_open': normalize_time_value(row.get('market_open'), defaults['market_open']),
            'market_close': normalize_time_value(row.get('market_close'), defaults['market_close']),
            'timezone': 'Asia/Kolkata',
        }
    except Error as e:
        print(f"Market settings fetch error: {e}")
        return defaults
    finally:
        cursor.close()
        conn.close()

# ============= DATABASE CONNECTION =============
def get_db_connection():
    """Create and return a database connection"""
    try:
        return mysql.connector.connect(
            host=Config.MYSQL_HOST,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD,
            database=Config.MYSQL_DB
        )
    except Error as e:
        print(f"Database error: {e}")
        return None

# ============= SECURITY DECORATORS =============
def login_required(f):
    """Decorator to protect user routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login_user'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorator to protect admin routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_id' not in session:
            return redirect(url_for('login_admin'))
        return f(*args, **kwargs)
    return decorated_function

# ============= PUBLIC PAGES =============
@app.route('/')
def index():
    """Home Page (Landing Page)"""
    return render_template('index.html')

@app.route('/login/user')
def login_user():
    """User Login Page"""
    return render_template('login.html')

@app.route('/signup/user')
def signup_user():
    """User Sign Up Page"""
    return render_template('signup_user.html')

@app.route('/login/admin')
def login_admin():
    """Admin Login Page"""
    return render_template('login_admin.html')

@app.route('/logout')
def logout():
    """Logout any user"""
    session.clear()
    return redirect(url_for('index'))

# ============= AUTHENTICATION APIs =============
@app.route('/api/register', methods=['POST'])
def register():
    """User Registration"""
    data = request.get_json()
    username = (data.get('username') or '').strip()
    email = (data.get('email') or '').strip().lower()
    password = data.get('password')
    phone = (data.get('phone') or '').strip()
    social_provider = data.get('social_provider')
    accepted_terms = data.get('accepted_terms')
    
    if not all([username, email, password]):
        return jsonify({'error': 'Username, email, and password are required'}), 400
    if not re.fullmatch(r"[A-Za-z ]{2,50}", username):
        return jsonify({'error': 'Name must contain only letters and spaces'}), 400
    if not re.fullmatch(r"[A-Za-z0-9._%+-]+@gmail\.com", email):
        return jsonify({'error': 'Email must be a valid @gmail.com address'}), 400
    if phone and not re.fullmatch(r"\d{10}", phone):
        return jsonify({'error': 'Phone number must contain exactly 10 digits'}), 400
    if not accepted_terms:
        return jsonify({'error': 'You must accept the terms, risk, and privacy notice'}), 400
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    conn.close()

    if not ensure_user_schema():
        return jsonify({'error': 'User database schema setup failed'}), 500

    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id FROM users WHERE username = %s OR email = %s", (username, email))
        if cursor.fetchone():
            return jsonify({'error': 'Username or email already exists'}), 409
        
        password_hash = generate_password_hash(password)
        cursor.execute("""
            INSERT INTO users (username, email, password_hash, phone, social_provider)
            VALUES (%s, %s, %s, %s, %s)
        """, (username, email, password_hash, phone, social_provider))
        conn.commit()
        user_id = cursor.lastrowid
        
        return jsonify({
            'message': 'Registration successful',
            'user': {
                'id': user_id,
                'username': username,
                'email': email,
                'phone': phone,
                'social_provider': social_provider
            }
        }), 201
    except Error as e:
        conn.rollback()
        print(f"Registration error: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/api/login/user', methods=['POST'])
def api_login_user():
    """User Login API"""
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['user_type'] = 'user'
            return jsonify({
                'message': 'Login successful',
                'user': {
                    'id': user['id'],
                    'username': user['username'],
                    'email': user['email'],
                    'balance': float(user.get('balance', 10000))
                }
            }), 200
        
        return jsonify({'error': 'Invalid username or password'}), 401
    finally:
        cursor.close()
        conn.close()

@app.route('/api/login/admin', methods=['POST'])
def api_login_admin():
    """Admin Login API"""
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM admins WHERE username = %s", (username,))
        admin = cursor.fetchone()
        
        if admin and check_password_hash(admin['password_hash'], password):
            session['admin_id'] = admin['id']
            session['admin_name'] = admin['username']
            session['user_type'] = 'admin'
            return jsonify({'message': 'Admin login successful'}), 200
        
        return jsonify({'error': 'Invalid admin credentials'}), 401
    finally:
        cursor.close()
        conn.close()

# ============= PROFILE ROUTES =============
@app.route('/profile/edit')
@login_required
def profile_edit():
    """Edit Profile Page"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT username, email, phone, profile_pic, created_at
            FROM users WHERE id = %s
        """, (session['user_id'],))
        user = cursor.fetchone()
        return render_template('profile/edit.html', user=user, username=session['username'])
    finally:
        cursor.close()
        conn.close()

@app.route('/profile/change_password')
@login_required
def profile_change_password():
    """Change Password Page"""
    return render_template('profile/change_password.html', username=session['username'])

@app.route('/api/profile/update', methods=['POST'])
@login_required
def update_profile():
    """Update user profile"""
    try:
        username = request.form.get('username')
        email = request.form.get('email')
        phone = request.form.get('phone')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE users SET username = %s, email = %s, phone = %s WHERE id = %s
        """, (username, email, phone, session['user_id']))
        
        if 'profile_pic' in request.files:
            file = request.files['profile_pic']
            if file and file.filename != '':
                filename = f"{session['user_id']}_{int(time.time())}_{file.filename}"
                filepath = os.path.join('static', 'uploads', 'profiles', filename)
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                file.save(filepath)
                cursor.execute("UPDATE users SET profile_pic = %s WHERE id = %s", (filename, session['user_id']))
        
        conn.commit()
        
        if username:
            session['username'] = username
        
        return jsonify({'message': 'Profile updated successfully'}), 200
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/api/profile/change_password', methods=['POST'])
@login_required
def change_password():
    """Change user password"""
    data = request.get_json()
    current_password = data.get('current_password')
    new_password = data.get('new_password')
    
    if not all([current_password, new_password]):
        return jsonify({'error': 'All fields are required'}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT password_hash FROM users WHERE id = %s", (session['user_id'],))
        user = cursor.fetchone()
        
        if not user or not check_password_hash(user['password_hash'], current_password):
            return jsonify({'error': 'Current password is incorrect'}), 401
        
        new_hash = generate_password_hash(new_password)
        cursor.execute("UPDATE users SET password_hash = %s WHERE id = %s", (new_hash, session['user_id']))
        conn.commit()
        
        return jsonify({'message': 'Password changed successfully'}), 200
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

# ============= DASHBOARD PAGES =============
@app.route('/dashboard')
@login_required
def dashboard():
    """User Trading Dashboard"""
    ensure_default_stocks()
    response = make_response(render_template(
        'dashboard.html',
        username=session['username'],
        platform_settings=get_platform_settings_snapshot()
    ))
    return apply_no_cache(response)

@app.route('/explore')
@login_required
def explore():
    """Explore Stocks Page"""
    ensure_default_stocks()
    response = make_response(render_template(
        'explore.html',
        username=session['username'],
        platform_settings=get_platform_settings_snapshot()
    ))
    return apply_no_cache(response)

@app.route('/holdings')
@login_required
def holdings():
    """Holdings Page"""
    return render_template('holdings.html', username=session['username'])

@app.route('/positions')
@login_required
def positions():
    """Positions Page"""
    return render_template('positions.html', username=session['username'])

@app.route('/orders')
@login_required
def orders():
    """Orders Page"""
    return render_template('orders.html', username=session['username'])

@app.route('/watchlist/my')
@login_required
def watchlist_my():
    """My Watchlist Page"""
    return render_template('watchlist_my.html', username=session['username'])

@app.route('/watchlist/all')
@login_required
def watchlist_all():
    """All Watchlists Page"""
    return render_template('watchlist_all.html', username=session['username'])

# ============= ADMIN DASHBOARD ROUTES =============
@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    """Admin Dashboard with Summary Cards"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT COUNT(*) as total FROM users")
        total_users = cursor.fetchone()['total']
        
        cursor.execute("SELECT COUNT(DISTINCT user_id) as active FROM transactions WHERE DATE(transaction_date) = CURDATE()")
        active_traders = cursor.fetchone()['active'] or 0
        
        cursor.execute("SELECT COUNT(*) as trades FROM transactions WHERE DATE(transaction_date) = CURDATE()")
        trades_today = cursor.fetchone()['trades'] or 0
        
        cursor.execute("SELECT COUNT(*) as buys FROM transactions WHERE transaction_type = 'BUY' AND DATE(transaction_date) = CURDATE()")
        buy_orders = cursor.fetchone()['buys'] or 0
        
        cursor.execute("SELECT COUNT(*) as sells FROM transactions WHERE transaction_type = 'SELL' AND DATE(transaction_date) = CURDATE()")
        sell_orders = cursor.fetchone()['sells'] or 0
        
        cursor.execute("SELECT SUM(total_amount * 0.001) as revenue FROM transactions WHERE DATE(transaction_date) = CURDATE()")
        platform_revenue = cursor.fetchone()['revenue'] or 0
        
        cursor.execute("SELECT COUNT(*) as stocks FROM stocks")
        listed_stocks = cursor.fetchone()['stocks']
        
        cursor.execute("SELECT id, username, email, balance, created_at FROM users ORDER BY created_at DESC LIMIT 10")
        recent_users = cursor.fetchall()
        
        return render_template('admin_dashboard.html',
            admin_name=session['admin_name'],
            total_users=total_users,
            active_traders=active_traders,
            trades_today=trades_today,
            buy_orders=buy_orders,
            sell_orders=sell_orders,
            platform_revenue=round(platform_revenue, 2),
            listed_stocks=listed_stocks,
            recent_users=recent_users)
    finally:
        cursor.close()
        conn.close()

@app.route('/admin/users')
@admin_required
def admin_users():
    """User Management Page"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        search = request.args.get('search', '')
        if search:
            if str(search).isdigit():
                cursor.execute("""
                    SELECT id, username, email, balance, created_at, COALESCE(is_active, TRUE) AS is_active
                    FROM users
                    WHERE id = %s OR username LIKE %s OR email LIKE %s
                    ORDER BY created_at DESC
                """, (int(search), f'%{search}%', f'%{search}%'))
            else:
                cursor.execute("""
                    SELECT id, username, email, balance, created_at, COALESCE(is_active, TRUE) AS is_active
                    FROM users
                    WHERE username LIKE %s OR email LIKE %s
                    ORDER BY created_at DESC
                """, (f'%{search}%', f'%{search}%'))
        else:
            cursor.execute("""
                SELECT id, username, email, balance, created_at, COALESCE(is_active, TRUE) AS is_active
                FROM users
                ORDER BY created_at DESC
            """)
        users = cursor.fetchall()
        return render_template('admin_users.html', users=users, admin_name=session['admin_name'], search=search)
    finally:
        cursor.close()
        conn.close()

# ============= ADMIN USER MANAGEMENT ACTIONS =============
@app.route('/admin/users/<int:user_id>/edit', methods=['POST'])
@admin_required
def edit_user(user_id):
    """Edit user details"""
    data = request.get_json()
    username = data.get('username')
    email = data.get('email')
    balance = float(data.get('balance'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE users SET username = %s, email = %s, balance = %s WHERE id = %s
        """, (username, email, balance, user_id))
        conn.commit()
        return jsonify({'message': 'User updated successfully'}), 200
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/admin/users/<int:user_id>/toggle', methods=['POST'])
@admin_required
def toggle_user_status(user_id):
    """Activate/Deactivate user account"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE")
        cursor.execute("UPDATE users SET is_active = NOT is_active WHERE id = %s", (user_id,))
        conn.commit()
        return jsonify({'message': 'User status updated'}), 200
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/admin/users/<int:user_id>/reset-password', methods=['POST'])
@admin_required
def reset_user_password(user_id):
    """Reset user password"""
    temp_password = 'TempPass123!'
    new_hash = generate_password_hash(temp_password)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE users SET password_hash = %s WHERE id = %s", (new_hash, user_id))
        conn.commit()
        return jsonify({
            'message': f'Password reset for user #{user_id}',
            'temp_password': temp_password
        }), 200
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/admin/users/<int:user_id>/delete', methods=['DELETE'])
@admin_required
def delete_user(user_id):
    """Delete user account and all related data"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM transactions WHERE user_id = %s", (user_id,))
        cursor.execute("DELETE FROM holdings WHERE user_id = %s", (user_id,))
        cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
        conn.commit()
        return jsonify({'message': 'User deleted successfully'}), 200
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/admin/users/<int:user_id>/portfolio')
@admin_required
def view_user_portfolio(user_id):
    """View user's portfolio"""
    return f"<h1>Portfolio for User #{user_id}</h1><p>Coming soon!</p>"

@app.route('/admin/users/<int:user_id>/transactions')
@admin_required
def view_user_transactions(user_id):
    """View user's transaction history"""
    return f"<h1>Transactions for User #{user_id}</h1><p>Coming soon!</p>"

# ============= ADMIN STOCK MANAGEMENT =============
@app.route('/admin/stocks')
@admin_required
def admin_stocks():
    """Stock Management Page"""
    ensure_default_stocks()
    ensure_stock_management_schema()
    market_settings = get_market_settings_data()
    current_market_time = datetime.datetime.now(ZoneInfo(market_settings['timezone']))
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM stocks ORDER BY symbol")
        stocks = cursor.fetchall()
        return render_template(
            'admin_stocks.html',
            stocks=stocks,
            admin_name=session['admin_name'],
            market_settings=market_settings,
            current_market_time=current_market_time,
        )
    finally:
        cursor.close()
        conn.close()

@app.route('/admin/stocks/add', methods=['POST'])
@admin_required
def add_stock():
    """Add new stock"""
    ensure_stock_management_schema()
    data = request.get_json()
    symbol = data.get('symbol', '').upper()
    name = data.get('name')
    current_price = float(data.get('current_price'))
    sector = data.get('sector', '')
    category = data.get('category', '')
    
    if not all([symbol, name, current_price]):
        return jsonify({'error': 'Symbol, name, and price are required'}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id FROM stocks WHERE symbol = %s", (symbol,))
        if cursor.fetchone():
            return jsonify({'error': 'Stock symbol already exists'}), 409
        
        cursor.execute("""
            INSERT INTO stocks (symbol, name, current_price, sector, category, change_percent)
            VALUES (%s, %s, %s, %s, %s, 0.00)
        """, (symbol, name, current_price, sector, category))
        conn.commit()
        return jsonify({'message': 'Stock added successfully'}), 201
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/admin/stocks/<int:stock_id>/edit', methods=['POST'])
@admin_required
def edit_stock(stock_id):
    """Edit stock details"""
    ensure_stock_management_schema()
    data = request.get_json()
    name = data.get('name')
    current_price = float(data.get('current_price'))
    sector = data.get('sector', '')
    category = data.get('category', '')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE stocks SET name = %s, current_price = %s, sector = %s, category = %s
            WHERE id = %s
        """, (name, current_price, sector, category, stock_id))
        conn.commit()
        return jsonify({'message': 'Stock updated successfully'}), 200
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/admin/stocks/<int:stock_id>/price', methods=['POST'])
@admin_required
def update_stock_price(stock_id):
    """Update stock price only"""
    ensure_stock_management_schema()
    data = request.get_json()
    current_price = float(data.get('current_price'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE stocks SET current_price = %s, last_updated = NOW() WHERE id = %s", (current_price, stock_id))
        conn.commit()
        return jsonify({'message': 'Price updated successfully'}), 200
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/admin/stocks/<int:stock_id>/delete', methods=['DELETE'])
@admin_required
def delete_stock(stock_id):
    """Delete stock"""
    ensure_stock_management_schema()
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM holdings WHERE stock_id = %s", (stock_id,))
        cursor.execute("DELETE FROM stocks WHERE id = %s", (stock_id,))
        conn.commit()
        return jsonify({'message': 'Stock deleted successfully'}), 200
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/admin/stocks/settings', methods=['POST'])
@admin_required
def save_market_settings():
    """Save market open/close settings"""
    ensure_stock_management_schema()
    data = request.get_json()
    market_open = data.get('market_open')
    market_close = data.get('market_close')
    timezone = 'Asia/Kolkata'

    if not market_open or not market_close:
        return jsonify({'error': 'Market open and close times are required'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO market_settings (id, market_open, market_close, timezone)
            VALUES (1, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                market_open = VALUES(market_open),
                market_close = VALUES(market_close),
                timezone = VALUES(timezone),
                updated_at = NOW()
        """, (market_open, market_close, timezone))
        conn.commit()
        current_time = datetime.datetime.now(ZoneInfo(timezone)).strftime('%Y-%m-%d %H:%M:%S')
        return jsonify({
            'message': 'Market settings saved',
            'settings': {
                'market_open': market_open,
                'market_close': market_close,
                'timezone': timezone,
                'current_time': current_time,
            }
        }), 200
    except Error as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/admin/stocks/upload', methods=['POST'])
@admin_required
def upload_stock_csv():
    """Upload and import stocks from CSV"""
    ensure_stock_management_schema()
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    update_existing = request.form.get('update_existing', 'false') == 'true'
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    if not file.filename.endswith('.csv'):
        return jsonify({'error': 'Please upload a CSV file'}), 400
    
    try:
        stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
        csv_reader = csv.DictReader(stream)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        added = 0
        updated = 0
        errors = 0
        
        for row in csv_reader:
            try:
                symbol = row.get('symbol', '').strip().upper()
                name = row.get('name', '').strip()
                current_price = float(row.get('current_price', 0))
                sector = row.get('sector', '').strip()
                category = row.get('category', '').strip()
                
                if not all([symbol, name, current_price]):
                    errors += 1
                    continue
                
                if update_existing:
                    cursor.execute("SELECT id FROM stocks WHERE symbol = %s", (symbol,))
                    existing = cursor.fetchone()
                    if existing:
                        cursor.execute("""
                            UPDATE stocks SET name = %s, current_price = %s, sector = %s, category = %s
                            WHERE symbol = %s
                        """, (name, current_price, sector, category, symbol))
                        updated += 1
                    else:
                        cursor.execute("""
                            INSERT INTO stocks (symbol, name, current_price, sector, category, change_percent)
                            VALUES (%s, %s, %s, %s, %s, 0.00)
                        """, (symbol, name, current_price, sector, category))
                        added += 1
                else:
                    cursor.execute("SELECT id FROM stocks WHERE symbol = %s", (symbol,))
                    if not cursor.fetchone():
                        cursor.execute("""
                            INSERT INTO stocks (symbol, name, current_price, sector, category, change_percent)
                            VALUES (%s, %s, %s, %s, %s, 0.00)
                        """, (symbol, name, current_price, sector, category))
                        added += 1
                    else:
                        errors += 1
            except Exception as e:
                errors += 1
                print(f"CSV import error: {e}")
                continue
        
        conn.commit()
        return jsonify({
            'message': 'Import completed',
            'added': added,
            'updated': updated,
            'errors': errors
        }), 200
    except Exception as e:
        return jsonify({'error': f'Import failed: {str(e)}'}), 500
    finally:
        cursor.close()
        conn.close()

# ============= ADMIN TRANSACTION MANAGEMENT =============
@app.route('/admin/transactions')
@admin_required
def admin_transactions():
    """Transaction Management Page"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        symbol = request.args.get('symbol', '').strip().upper()
        
        query = """
            SELECT t.*, u.username, u.email, s.symbol, s.name as stock_name
            FROM transactions t
            JOIN users u ON t.user_id = u.id
            JOIN stocks s ON t.stock_id = s.id
            WHERE 1=1
        """
        params = []
        
        if symbol:
            query += " AND s.symbol LIKE %s"
            params.append(f"%{symbol}%")
        
        query += " ORDER BY t.transaction_date DESC LIMIT 500"
        cursor.execute(query, tuple(params))
        transactions = cursor.fetchall()
        
        cursor.execute("SELECT id, username FROM users ORDER BY username")
        users = cursor.fetchall()
        
        return render_template('admin_transactions.html',
            transactions=transactions,
            users=users,
            admin_name=session['admin_name'],
            filters={'symbol': symbol})
    finally:
        cursor.close()
        conn.close()

@app.route('/admin/transactions/export')
@admin_required
def export_transactions():
    """Export transactions to CSV"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        symbol = request.args.get('symbol', '').strip().upper()

        query = """
            SELECT t.transaction_date, u.username, u.email, s.symbol, s.name AS stock_name,
            t.transaction_type, t.quantity, t.price_per_unit, t.total_amount, t.status
            FROM transactions t
            JOIN users u ON t.user_id = u.id
            JOIN stocks s ON t.stock_id = s.id
            WHERE 1=1
        """
        params = []

        if symbol:
            query += " AND s.symbol LIKE %s"
            params.append(f"%{symbol}%")

        query += " ORDER BY t.transaction_date DESC"
        cursor.execute(query, tuple(params))
        transactions = cursor.fetchall()
        
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Date', 'User', 'Email', 'Symbol', 'Stock Name', 'Type', 'Quantity', 'Price', 'Total', 'Status'])
        
        for t in transactions:
            writer.writerow([
                t['transaction_date'].strftime('%Y-%m-%d %H:%M'),
                t['username'],
                t['email'],
                t['symbol'],
                t['stock_name'],
                t['transaction_type'],
                t['quantity'],
                t['price_per_unit'],
                t['total_amount'],
                t.get('status', 'APPROVED')
            ])
        
        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename=transactions.csv'}
        )
    finally:
        cursor.close()
        conn.close()

@app.route('/admin/transactions/<int:transaction_id>/approve', methods=['POST'])
@admin_required
def approve_transaction(transaction_id):
    """Approve a pending transaction"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE transactions SET status = 'APPROVED' WHERE id = %s AND status = 'PENDING'", (transaction_id,))
        conn.commit()
        return jsonify({'message': 'Transaction approved'}), 200
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/admin/transactions/<int:transaction_id>/reject', methods=['POST'])
@admin_required
def reject_transaction(transaction_id):
    """Reject a pending transaction"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE transactions SET status = 'REJECTED' WHERE id = %s AND status = 'PENDING'", (transaction_id,))
        conn.commit()
        return jsonify({'message': 'Transaction rejected'}), 200
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

# ============= ADMIN ANALYTICS & REPORTS =============
@app.route('/admin/analytics')
@admin_required
def admin_analytics():
    """Analytics & Reports Page"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT DATE(transaction_date) as date, COUNT(*) as volume, SUM(total_amount) as value
            FROM transactions
            WHERE transaction_date >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
            GROUP BY DATE(transaction_date)
            ORDER BY date
        """)
        daily_volume = cursor.fetchall()
        
        cursor.execute("""
            SELECT s.symbol, s.name, COUNT(*) as trade_count, SUM(t.quantity) as total_quantity
            FROM transactions t
            JOIN stocks s ON t.stock_id = s.id
            WHERE t.transaction_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
            GROUP BY s.id
            ORDER BY trade_count DESC
            LIMIT 10
        """)
        most_traded = cursor.fetchall()
        
        cursor.execute("""
            SELECT u.username,
            SUM(CASE WHEN t.transaction_type = 'SELL' THEN t.total_amount
            WHEN t.transaction_type = 'BUY' THEN -t.total_amount END) as net_value,
            COUNT(*) as trade_count
            FROM transactions t
            JOIN users u ON t.user_id = u.id
            GROUP BY u.id
            ORDER BY net_value DESC
            LIMIT 10
        """)
        top_users = cursor.fetchall()
        
        cursor.execute("""
            SELECT DATE_FORMAT(created_at, '%Y-%m') as month, COUNT(*) as new_users
            FROM users
            GROUP BY DATE_FORMAT(created_at, '%Y-%m')
            ORDER BY month
            LIMIT 12
        """)
        platform_growth = cursor.fetchall()
        
        cursor.execute("""
            SELECT DATE_FORMAT(transaction_date, '%Y-%m') as month,
            COUNT(DISTINCT user_id) as active_users
            FROM transactions
            WHERE transaction_date >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
            GROUP BY DATE_FORMAT(transaction_date, '%Y-%m')
            ORDER BY month
        """)
        mau = cursor.fetchall()
        
        return render_template('admin_analytics.html',
            daily_volume=daily_volume,
            most_traded=most_traded,
            top_users=top_users,
            platform_growth=platform_growth,
            mau=mau,
            admin_name=session['admin_name'])
    finally:
        cursor.close()
        conn.close()

@app.route('/admin/analytics/data/<chart_type>')
@admin_required
def get_analytics_data(chart_type):
    """Get analytics data for charts (API endpoint)"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        month_labels = []
        month_cursor = datetime.date.today().replace(day=1)
        for _ in range(6):
            month_labels.append(month_cursor.strftime('%Y-%m'))
            if month_cursor.month == 1:
                month_cursor = month_cursor.replace(year=month_cursor.year - 1, month=12)
            else:
                month_cursor = month_cursor.replace(month=month_cursor.month - 1)
        month_labels.reverse()

        if chart_type == 'daily_volume':
            cursor.execute("""
                SELECT DATE(transaction_date) as date, COUNT(*) as volume
                FROM transactions
                WHERE transaction_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
                GROUP BY DATE(transaction_date)
                ORDER BY date
            """)
            data = cursor.fetchall()
            return jsonify({
                'labels': [d['date'].strftime('%Y-%m-%d') for d in data],
                'values': [d['volume'] for d in data]
            })
        elif chart_type == 'most_traded':
            cursor.execute("""
                SELECT s.symbol, COUNT(*) as count
                FROM transactions t
                JOIN stocks s ON t.stock_id = s.id
                WHERE t.transaction_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
                GROUP BY s.id
                ORDER BY count DESC
                LIMIT 10
            """)
            data = cursor.fetchall()
            return jsonify({
                'labels': [d['symbol'] for d in data],
                'values': [d['count'] for d in data]
            })
        elif chart_type == 'top_users':
            cursor.execute("""
                SELECT u.username,
                SUM(CASE WHEN t.transaction_type = 'SELL' THEN t.total_amount
                WHEN t.transaction_type = 'BUY' THEN -t.total_amount END) as profit
                FROM transactions t
                JOIN users u ON t.user_id = u.id
                GROUP BY u.id
                ORDER BY profit DESC
                LIMIT 10
            """)
            data = cursor.fetchall()
            return jsonify({
                'labels': [d['username'] for d in data],
                'values': [round(d['profit'], 2) for d in data]
            })
        elif chart_type == 'platform_growth':
            cursor.execute("""
                SELECT DATE_FORMAT(created_at, '%Y-%m') as month, COUNT(*) as users
                FROM users
                WHERE created_at >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH)
                GROUP BY DATE_FORMAT(created_at, '%Y-%m')
                ORDER BY month
            """)
            data = cursor.fetchall()
            values_map = {label: 0 for label in month_labels}
            for row in data:
                if row['month'] in values_map:
                    values_map[row['month']] = row['users']
            return jsonify({
                'labels': month_labels,
                'values': [values_map[label] for label in month_labels]
            })
        elif chart_type == 'mau':
            cursor.execute("""
                SELECT DATE_FORMAT(transaction_date, '%Y-%m') as month,
                COUNT(DISTINCT user_id) as active
                FROM transactions
                WHERE transaction_date >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH)
                GROUP BY DATE_FORMAT(transaction_date, '%Y-%m')
                ORDER BY month
            """)
            data = cursor.fetchall()
            values_map = {label: 0 for label in month_labels}
            for row in data:
                if row['month'] in values_map:
                    values_map[row['month']] = row['active']
            return jsonify({
                'labels': month_labels,
                'values': [values_map[label] for label in month_labels]
            })
        elif chart_type == 'buyers_sellers':
            cursor.execute("""
                SELECT DATE_FORMAT(transaction_date, '%Y-%m') as month,
                SUM(CASE WHEN transaction_type = 'BUY' THEN quantity ELSE 0 END) as buy_quantity,
                SUM(CASE WHEN transaction_type = 'SELL' THEN quantity ELSE 0 END) as sell_quantity
                FROM transactions
                WHERE transaction_date >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH)
                GROUP BY DATE_FORMAT(transaction_date, '%Y-%m')
                ORDER BY month
            """)
            data = cursor.fetchall()
            buy_map = {label: 0 for label in month_labels}
            sell_map = {label: 0 for label in month_labels}
            for row in data:
                if row['month'] in buy_map:
                    buy_map[row['month']] = float(row['buy_quantity'] or 0)
                    sell_map[row['month']] = float(row['sell_quantity'] or 0)
            return jsonify({
                'labels': month_labels,
                'buy_values': [buy_map[label] for label in month_labels],
                'sell_values': [sell_map[label] for label in month_labels]
            })
        return jsonify({'error': 'Unknown chart type'}), 400
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

# ============= ADMIN FUND MANAGEMENT =============
@app.route('/admin/funds')
@admin_required
def admin_funds():
    """Fund Management Page"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT id, username, email, balance,
            (SELECT COUNT(*) FROM transactions WHERE user_id = users.id) as transaction_count
            FROM users
            ORDER BY balance DESC
        """)
        users = cursor.fetchall()
        
        try:
            cursor.execute("""
                SELECT r.*, u.username, u.email
                FROM fund_requests r
                JOIN users u ON r.user_id = u.id
                WHERE r.status = 'PENDING'
                ORDER BY r.created_at DESC
            """)
            pending_requests = cursor.fetchall()
        except Error:
            pending_requests = []

        cursor.execute("SELECT COALESCE(SUM(balance), 0) AS total_user_balance FROM users")
        total_user_balance = float(cursor.fetchone()['total_user_balance'] or 0)

        brokerage_percent = 0.10
        try:
            cursor.execute("SELECT brokerage_percent FROM system_settings LIMIT 1")
            settings_row = cursor.fetchone()
            if settings_row and settings_row.get('brokerage_percent') is not None:
                brokerage_percent = float(settings_row['brokerage_percent'])
        except Error:
            pass

        total_deposits = 0.0
        total_withdrawals = 0.0
        pending_withdrawals = 0.0
        try:
            cursor.execute("""
                SELECT
                    COALESCE(SUM(CASE WHEN type IN ('DEPOSIT', 'CREDIT') AND status = 'APPROVED' THEN amount ELSE 0 END), 0) AS total_deposits,
                    COALESCE(SUM(CASE WHEN type IN ('WITHDRAWAL', 'DEBIT') AND status = 'APPROVED' THEN amount ELSE 0 END), 0) AS total_withdrawals,
                    COALESCE(SUM(CASE WHEN type = 'WITHDRAWAL' AND status = 'PENDING' THEN amount ELSE 0 END), 0) AS pending_withdrawals
                FROM fund_requests
            """)
            fund_totals = cursor.fetchone() or {}
            total_deposits = float(fund_totals.get('total_deposits') or 0)
            total_withdrawals = float(fund_totals.get('total_withdrawals') or 0)
            pending_withdrawals = float(fund_totals.get('pending_withdrawals') or 0)
        except Error:
            pass

        cursor.execute("""
            SELECT COUNT(*) AS today_transactions
            FROM transactions
            WHERE DATE(transaction_date) = CURDATE()
        """)
        transaction_snapshot = cursor.fetchone() or {}
        today_transactions = int(transaction_snapshot.get('today_transactions') or 0)

        cursor.execute("""
            SELECT COALESCE(SUM(total_amount), 0) AS monthly_turnover
            FROM transactions
            WHERE DATE_FORMAT(transaction_date, '%Y-%m') = DATE_FORMAT(CURDATE(), '%Y-%m')
        """)
        monthly_turnover_row = cursor.fetchone() or {}
        monthly_turnover = float(monthly_turnover_row.get('monthly_turnover') or 0)
        monthly_revenue = round(monthly_turnover * (brokerage_percent / 100), 2)
        total_platform_funds = round((total_deposits - total_withdrawals) + monthly_revenue, 2)

        return render_template('admin_funds.html',
            users=users,
            pending_requests=pending_requests,
            fund_summary={
                'total_platform_funds': total_platform_funds,
                'total_user_balance': total_user_balance,
                'total_deposits': total_deposits,
                'total_withdrawals': total_withdrawals,
                'pending_withdrawals': pending_withdrawals,
                'today_transactions': today_transactions,
                'monthly_revenue': monthly_revenue,
            },
            admin_name=session['admin_name'])
    finally:
        cursor.close()
        conn.close()

@app.route('/admin/funds/add-money', methods=['POST'])
@admin_required
def add_money():
    """Add virtual money to user"""
    data = request.get_json()
    user_id = data.get('user_id')
    amount = float(data.get('amount'))
    reason = data.get('reason', 'Admin adjustment')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE users SET balance = balance + %s WHERE id = %s", (amount, user_id))
        try:
            cursor.execute("""
                INSERT INTO fund_requests (user_id, amount, type, reason, status, admin_id)
                VALUES (%s, %s, 'CREDIT', %s, 'APPROVED', %s)
            """, (user_id, amount, reason, session['admin_id']))
        except Error:
            pass
        conn.commit()
        return jsonify({'message': f'INR {amount:.2f} added successfully'}), 200
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/admin/funds/deduct-money', methods=['POST'])
@admin_required
def deduct_money():
    """Deduct money from user"""
    data = request.get_json()
    user_id = data.get('user_id')
    amount = float(data.get('amount'))
    reason = data.get('reason', 'Admin adjustment')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT balance FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        if user[0] < amount:
            return jsonify({'error': 'Insufficient balance'}), 400
        
        cursor.execute("UPDATE users SET balance = balance - %s WHERE id = %s", (amount, user_id))
        try:
            cursor.execute("""
                INSERT INTO fund_requests (user_id, amount, type, reason, status, admin_id)
                VALUES (%s, %s, 'DEBIT', %s, 'APPROVED', %s)
            """, (user_id, amount, reason, session['admin_id']))
        except Error:
            pass
        conn.commit()
        return jsonify({'message': f'INR {amount:.2f} deducted successfully'}), 200
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/admin/funds/requests/<int:request_id>/approve', methods=['POST'])
@admin_required
def approve_fund_request(request_id):
    """Approve deposit/withdrawal request"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM fund_requests WHERE id = %s", (request_id,))
        request = cursor.fetchone()
        if not request:
            return jsonify({'error': 'Request not found'}), 404
        
        if request['type'] == 'DEPOSIT':
            cursor.execute("UPDATE users SET balance = balance + %s WHERE id = %s",
                (request['amount'], request['user_id']))
        elif request['type'] == 'WITHDRAWAL':
            cursor.execute("SELECT balance FROM users WHERE id = %s", (request['user_id'],))
            user = cursor.fetchone()
            if not user or float(user['balance']) < float(request['amount']):
                return jsonify({'error': 'Insufficient balance'}), 400
            cursor.execute("UPDATE users SET balance = balance - %s WHERE id = %s",
                (request['amount'], request['user_id']))
        
        cursor.execute("UPDATE fund_requests SET status = 'APPROVED', processed_at = NOW() WHERE id = %s", (request_id,))
        conn.commit()
        return jsonify({'message': 'Request approved'}), 200
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/admin/funds/requests/<int:request_id>/reject', methods=['POST'])
@admin_required
def reject_fund_request(request_id):
    """Reject deposit/withdrawal request"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE fund_requests SET status = 'REJECTED', processed_at = NOW() WHERE id = %s", (request_id,))
        conn.commit()
        return jsonify({'message': 'Request rejected'}), 200
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

# ============= ADMIN CONTROLS & SETTINGS =============
@app.route('/admin/settings')
@admin_required
def admin_settings():
    """Admin Controls Page"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        try:
            ensure_system_settings_table(cursor)
            cursor.execute("SELECT * FROM system_settings WHERE id = 1 LIMIT 1")
            settings = cursor.fetchone()
            if not settings:
                settings = {'trading_enabled': True, 'brokerage_percent': 0.10}
        except Error:
            settings = {'trading_enabled': True, 'brokerage_percent': 0.10}
        
        try:
            cursor.execute("SELECT id, username, role, last_login FROM admins ORDER BY username")
            admins = cursor.fetchall()
        except Error:
            try:
                cursor.execute("SELECT id, username FROM admins ORDER BY username")
                admins = cursor.fetchall()
                for admin in admins:
                    admin['role'] = 'super_admin'
                    admin['last_login'] = None
            except Error:
                admins = []
        
        try:
            cursor.execute("""
                SELECT a.*, u.username as created_by
                FROM announcements a
                LEFT JOIN admins u ON a.created_by = u.id
                WHERE COALESCE(a.expires_at, DATE_ADD(a.created_at, INTERVAL 1 DAY)) > NOW()
                ORDER BY a.created_at DESC
                LIMIT 10
            """)
            announcements = cursor.fetchall()
        except Error:
            announcements = []
        
        return render_template('admin_settings.html',
            settings=settings,
            admins=admins,
            announcements=announcements,
            admin_name=session['admin_name'])
    except Error as e:
        print(f"Admin settings error: {e}")
        return render_template('admin_settings.html',
            settings={'trading_enabled': True, 'brokerage_percent': 0.10},
            admins=[],
            announcements=[],
            admin_name=session['admin_name'])
    finally:
        cursor.close()
        conn.close()

@app.route('/admin/settings/password', methods=['POST'])
@admin_required
def change_admin_password():
    """Change admin password"""
    data = request.get_json()
    current_password = data.get('current_password')
    new_password = data.get('new_password')
    
    if not all([current_password, new_password]):
        return jsonify({'error': 'All fields are required'}), 400
    if len(new_password) < 8:
        return jsonify({'error': 'Password must be at least 8 characters'}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT password_hash FROM admins WHERE id = %s", (session['admin_id'],))
        admin = cursor.fetchone()
        
        if not admin or not check_password_hash(admin['password_hash'], current_password):
            return jsonify({'error': 'Current password is incorrect'}), 401
        
        new_hash = generate_password_hash(new_password)
        cursor.execute("UPDATE admins SET password_hash = %s WHERE id = %s", (new_hash, session['admin_id']))
        conn.commit()
        
        return jsonify({'message': 'Password changed successfully'}), 200
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/admin/settings/role', methods=['POST'])
@admin_required
def manage_admin_role():
    """Manage admin roles"""
    data = request.get_json()
    admin_id = data.get('admin_id')
    role = data.get('role')
    
    if role not in ['super_admin', 'sub_admin']:
        return jsonify({'error': 'Invalid role'}), 400
    if admin_id == session['admin_id']:
        return jsonify({'error': 'Cannot change your own role'}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE admins ADD COLUMN IF NOT EXISTS role ENUM('super_admin', 'sub_admin') DEFAULT 'sub_admin'")
        cursor.execute("UPDATE admins SET role = %s WHERE id = %s", (role, admin_id))
        conn.commit()
        return jsonify({'message': 'Role updated successfully'}), 200
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/admin/settings/trading-toggle', methods=['POST'])
@admin_required
def toggle_trading():
    """Enable/Disable trading platform-wide"""
    data = request.get_json()
    enabled = data.get('enabled', True)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        ensure_system_settings_table(cursor)
        cursor.execute("""
            INSERT INTO system_settings (id, trading_enabled) VALUES (1, %s)
            ON DUPLICATE KEY UPDATE trading_enabled = %s, updated_at = NOW()
        """, (enabled, enabled))
        conn.commit()
        return jsonify({'message': f'Trading {"enabled" if enabled else "disabled"}'}), 200
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/admin/settings/announcement', methods=['POST'])
@admin_required
def send_announcement():
    """Send announcement to all users"""
    data = request.get_json()
    title = (data.get('title') or '').strip()
    message = (data.get('message') or '').strip()
    
    if not all([title, message]):
        return jsonify({'error': 'Title and message are required'}), 400
    if len(title) > 255:
        return jsonify({'error': 'Title must be less than 255 characters'}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        ensure_announcement_tables(cursor)
        cursor.execute("""
            INSERT INTO announcements (title, message, priority, created_by, expires_at)
            VALUES (%s, %s, %s, %s, DATE_ADD(NOW(), INTERVAL 1 DAY))
        """, (title, message, 'normal', session['admin_id']))
        conn.commit()
        return jsonify({'message': 'Announcement sent to all users for 24 hours'}), 201
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/admin/settings/brokerage', methods=['POST'])
@admin_required
def update_brokerage():
    """Update brokerage percentage"""
    data = request.get_json()
    brokerage = float(data.get('brokerage_percent'))
    
    if not (0 <= brokerage <= 5):
        return jsonify({'error': 'Brokerage must be between 0 and 5 percent'}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        ensure_system_settings_table(cursor)
        cursor.execute("""
            INSERT INTO system_settings (id, brokerage_percent) VALUES (1, %s)
            ON DUPLICATE KEY UPDATE brokerage_percent = %s, updated_at = NOW()
        """, (brokerage, brokerage))
        conn.commit()
        return jsonify({'message': f'Brokerage updated to {brokerage}%'}), 200
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

# ============= STOCK CANDLES API (CANDLESTICK CHART DATA) =============
@app.route('/api/stock/<symbol>/candles')
@login_required
def get_stock_candles(symbol):
    """Get OHLCV candlestick data for charts"""
    timeframe = request.args.get('timeframe', '1D')
    limit = request.args.get('limit', 100, type=int)
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id FROM stocks WHERE symbol = %s", (symbol,))
        if not cursor.fetchone():
            return jsonify({'error': 'Stock not found'}), 404
        
        # Generate realistic candlestick data (mock for demo)
        candles = generate_mock_candles(symbol, timeframe, limit)
        
        return jsonify({
            'symbol': symbol,
            'timeframe': timeframe,
            'candles': candles
        }), 200
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

def generate_mock_candles(symbol, timeframe, limit):
    """Generate realistic mock OHLCV candlestick data"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT current_price FROM stocks WHERE symbol = %s", (symbol,))
    stock = cursor.fetchone()
    cursor.close()
    conn.close()
    
    base_price = float(stock['current_price']) if stock else 100.0
    candles = []
    
    td_map = {
        '1m': datetime.timedelta(minutes=1),
        '2m': datetime.timedelta(minutes=2),
        '3m': datetime.timedelta(minutes=3),
        '5m': datetime.timedelta(minutes=5),
        '10m': datetime.timedelta(minutes=10),
        '15m': datetime.timedelta(minutes=15),
        '1h': datetime.timedelta(hours=1),
        '1D': datetime.timedelta(days=1),
        '1W': datetime.timedelta(weeks=1),
        '1M': datetime.timedelta(days=30)
    }
    interval = td_map.get(timeframe, datetime.timedelta(days=1))
    
    volatility = {
        '1m': 0.006, '2m': 0.007, '3m': 0.008, '5m': 0.010, '10m': 0.012, '15m': 0.014,
        '1h': 0.02, '1D': 0.03, '1W': 0.05, '1M': 0.08
    }
    vol = volatility.get(timeframe, 0.03)
    
    current_time = current_local_time()
    price = base_price
    
    for i in range(limit):
        change = (random.random() - 0.48) * price * vol
        open_price = price
        close_price = price + change
        high_price = max(open_price, close_price) * (1 + random.random() * vol * 0.5)
        low_price = min(open_price, close_price) * (1 - random.random() * vol * 0.5)
        volume = random.randint(10000, 1000000)
        
        candles.append({
            'time': (current_time - interval * (limit - i)).isoformat(),
            'open': round(open_price, 2),
            'high': round(high_price, 2),
            'low': round(low_price, 2),
            'close': round(close_price, 2),
            'volume': volume
        })
        price = close_price
    
    return candles

# ============= STOCK DETAIL PAGE =============
@app.route('/stock/<symbol>')
@login_required
def stock_detail(symbol):
    """Detailed Stock View Page"""
    response = make_response(render_template(
        'stock_detail.html',
        symbol=symbol,
        username=session['username'],
        platform_settings=get_platform_settings_snapshot()
    ))
    return apply_no_cache(response)

# ============= STOCK DETAIL API =============
@app.route('/api/stock/<symbol>')
@login_required
def get_stock_detail(symbol):
    """Get Detailed Stock Information"""
    timeframe = request.args.get('timeframe', '1D')
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM stocks WHERE symbol = %s", (symbol,))
        stock = cursor.fetchone()
        if not stock:
            return jsonify({'error': 'Stock not found'}), 404
        
        stock_data = {
            'symbol': stock['symbol'],
            'name': stock['name'],
            'current_price': float(stock['current_price']),
            'change_percent': float(stock['change_percent']),
            'change_amount': round(float(stock['current_price']) * float(stock['change_percent']) / 100, 2),
            'today_low': round(float(stock['current_price']) * 0.97, 2),
            'today_high': round(float(stock['current_price']) * 1.03, 2),
            'week_52_low': round(float(stock['current_price']) * 0.7, 2),
            'week_52_high': round(float(stock['current_price']) * 1.4, 2),
            'open': round(float(stock['current_price']) * 0.99, 2),
            'prev_close': round(float(stock['current_price']) * 1.01, 2),
            'volume': random.randint(1000000, 50000000),
            'lower_circuit': round(float(stock['current_price']) * 0.95, 2),
            'upper_circuit': round(float(stock['current_price']) * 1.05, 2),
            'market_cap': round(random.uniform(1000, 500000), 2),
            'roe': round(random.uniform(-5, 25), 2),
            'pe_ratio': round(random.uniform(-30, 50), 2),
            'eps': round(random.uniform(-10, 50), 2),
            'pb_ratio': round(random.uniform(0.5, 10), 2),
            'dividend_yield': round(random.uniform(0, 5), 2),
            'industry_pe': round(random.uniform(15, 35), 2),
            'book_value': round(float(stock['current_price']) * random.uniform(0.3, 0.8), 2),
            'debt_to_equity': round(random.uniform(0, 2), 2),
            'face_value': random.choice([1, 2, 5, 10]),
            'revenue': [
                {'quarter': 'Dec 24', 'value': round(random.uniform(500, 1000), 2)},
                {'quarter': 'Mar 25', 'value': round(random.uniform(500, 1000), 2)},
                {'quarter': 'Jun 25', 'value': round(random.uniform(500, 1000), 2)},
                {'quarter': 'Sep 25', 'value': round(random.uniform(500, 1000), 2)},
                {'quarter': 'Dec 25', 'value': round(random.uniform(500, 1000), 2)},
            ],
            'profit': [
                {'quarter': 'Dec 24', 'value': round(random.uniform(-100, 200), 2)},
                {'quarter': 'Mar 25', 'value': round(random.uniform(-100, 200), 2)},
                {'quarter': 'Jun 25', 'value': round(random.uniform(-100, 200), 2)},
                {'quarter': 'Sep 25', 'value': round(random.uniform(-100, 200), 2)},
                {'quarter': 'Dec 25', 'value': round(random.uniform(-100, 200), 2)},
            ],
            'chart_data': generate_chart_data(float(stock['current_price']), timeframe)
        }
        return jsonify(stock_data), 200
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

def generate_chart_data(current_price, timeframe='1D'):
    """Generate realistic chart data based on timeframe"""
    data = []
    base_price = current_price * 0.95
    
    timeframe_config = {
        '1D': {'days': 1, 'intervals': 78, 'volatility': 0.01},
        '1W': {'days': 7, 'intervals': 7, 'volatility': 0.02},
        '1M': {'days': 30, 'intervals': 30, 'volatility': 0.03},
        '3M': {'days': 90, 'intervals': 90, 'volatility': 0.04},
        '6M': {'days': 180, 'intervals': 180, 'volatility': 0.05},
        '1Y': {'days': 365, 'intervals': 365, 'volatility': 0.06},
        '5Y': {'days': 1825, 'intervals': 260, 'volatility': 0.08},
        'All': {'days': 1825, 'intervals': 260, 'volatility': 0.08}
    }
    
    config = timeframe_config.get(timeframe, timeframe_config['1D'])
    intervals = config['intervals']
    volatility = config['volatility']
    
    for i in range(intervals):
        if timeframe == '1D':
            time = current_local_time().replace(hour=9, minute=15, second=0, microsecond=0) + datetime.timedelta(minutes=i*5)
            time_label = time.strftime('%H:%M')
        else:
            time = current_local_time() - datetime.timedelta(days=intervals - i - 1)
            if timeframe in ['1W', '1M']:
                time_label = time.strftime('%b %d')
            elif timeframe in ['3M', '6M']:
                time_label = time.strftime('%b %Y')
            else:
                time_label = time.strftime('%Y')
        
        change = (random.random() - 0.48) * (current_price * volatility)
        base_price = max(base_price + change, current_price * 0.85)
        
        data.append({
            'time': time_label,
            'price': round(base_price, 2)
        })
    
    return data

# ============= TRADING APIs =============
@app.route('/api/stocks')
def get_stocks():
    """Get live stock data using the database as the source of truth."""
    stocks = fetch_live_stocks_from_db()
    if stocks is None:
        fallback_stocks = []
        for symbol, name, price in DEFAULT_STOCKS:
            fallback_stocks.append({
                'symbol': symbol,
                'name': name,
                'current_price': round(price, 2),
                'market_cap': 0.0,
                'change_percent': 0.0,
                'currency': 'INR',
                'category': 'other',
                'day_high': round(price * 1.02, 2),
                'day_low': round(price * 0.98, 2),
                'data_source': 'fallback',
            })
        return jsonify(fallback_stocks), 200
    return jsonify(stocks), 200


@app.route('/api/user/platform-settings')
@login_required
def get_user_platform_settings():
    """Expose current platform trading settings to logged-in users."""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500

    cursor = conn.cursor(dictionary=True)
    try:
        settings = get_platform_settings(cursor)
        ensure_announcement_tables(cursor)
        cursor.execute("""
            SELECT COUNT(*) AS unread_count
            FROM announcements a
            LEFT JOIN announcement_reads ar
                ON ar.announcement_id = a.id AND ar.user_id = %s
            WHERE ar.announcement_id IS NULL
        """, (session['user_id'],))
        unread_row = cursor.fetchone() or {}
        settings['unread_announcements'] = int(unread_row.get('unread_count', 0) or 0)
        return jsonify(settings), 200
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/api/user/announcements')
@login_required
def get_user_announcements():
    """Return announcements with read state for the logged-in user."""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500

    cursor = conn.cursor(dictionary=True)
    try:
        ensure_announcement_tables(cursor)
        cursor.execute("""
            SELECT a.id, a.title, a.message, a.priority, a.created_at, a.expires_at,
                   CASE WHEN ar.announcement_id IS NULL THEN FALSE ELSE TRUE END AS is_read,
                   ar.read_at
            FROM announcements a
            LEFT JOIN announcement_reads ar
                ON ar.announcement_id = a.id AND ar.user_id = %s
            WHERE COALESCE(a.expires_at, DATE_ADD(a.created_at, INTERVAL 1 DAY)) > NOW()
            ORDER BY a.created_at DESC
            LIMIT 20
        """, (session['user_id'],))
        announcements = cursor.fetchall()
        return jsonify(announcements), 200
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/api/user/announcements/<int:announcement_id>/read', methods=['POST'])
@login_required
def mark_announcement_read(announcement_id):
    """Mark an announcement as read for the logged-in user."""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500

    cursor = conn.cursor()
    try:
        ensure_announcement_tables(cursor)
        cursor.execute("SELECT id FROM announcements WHERE id = %s", (announcement_id,))
        if not cursor.fetchone():
            return jsonify({'error': 'Announcement not found'}), 404

        cursor.execute("""
            INSERT INTO announcement_reads (announcement_id, user_id)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE read_at = CURRENT_TIMESTAMP
        """, (announcement_id, session['user_id']))
        conn.commit()
        return jsonify({'message': 'Announcement marked as read'}), 200
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


def ensure_system_settings_table(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS system_settings (
            id INT PRIMARY KEY,
            trading_enabled BOOLEAN DEFAULT TRUE,
            brokerage_percent DECIMAL(5,2) DEFAULT 0.10,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        INSERT INTO system_settings (id, trading_enabled, brokerage_percent)
        VALUES (1, TRUE, 0.10)
        ON DUPLICATE KEY UPDATE id = id
    """)


def get_platform_settings(cursor):
    ensure_system_settings_table(cursor)
    cursor.execute("""
        SELECT brokerage_percent
        FROM system_settings
        WHERE id = 1
        LIMIT 1
    """)
    row = cursor.fetchone() or {}
    return {
        'trading_enabled': True,
        'brokerage_percent': float(row.get('brokerage_percent', 0.10) or 0.10)
    }


def get_platform_settings_snapshot():
    conn = get_db_connection()
    if not conn:
        return {'trading_enabled': True, 'brokerage_percent': 0.10}

    cursor = conn.cursor(dictionary=True)
    try:
        return get_platform_settings(cursor)
    except Error:
        return {'trading_enabled': True, 'brokerage_percent': 0.10}
    finally:
        cursor.close()
        conn.close()


def apply_no_cache(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


def ensure_announcement_tables(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS announcements (
            id INT AUTO_INCREMENT PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            message TEXT NOT NULL,
            priority ENUM('low', 'normal', 'high', 'urgent') DEFAULT 'normal',
            created_by INT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NULL DEFAULT NULL,
            FOREIGN KEY (created_by) REFERENCES admins(id)
        )
    """)
    try:
        cursor.execute("ALTER TABLE announcements ADD COLUMN expires_at TIMESTAMP NULL DEFAULT NULL")
    except Error:
        pass
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS announcement_reads (
            announcement_id INT NOT NULL,
            user_id INT NOT NULL,
            read_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (announcement_id, user_id),
            FOREIGN KEY (announcement_id) REFERENCES announcements(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

@app.route('/api/announcements/active')
def get_active_announcements():
    """Return active public announcements for support sections."""
    conn = get_db_connection()
    if not conn:
        return jsonify([]), 200

    cursor = conn.cursor(dictionary=True)
    try:
        ensure_announcement_tables(cursor)
        cursor.execute("""
            SELECT id, title, message, created_at, expires_at
            FROM announcements
            WHERE COALESCE(expires_at, DATE_ADD(created_at, INTERVAL 1 DAY)) > NOW()
            ORDER BY created_at DESC
            LIMIT 5
        """)
        return jsonify(cursor.fetchall()), 200
    except Error:
        return jsonify([]), 200
    finally:
        cursor.close()
        conn.close()

@app.route('/api/trade', methods=['POST'])
@login_required
def execute_trade():
    """Execute Buy/Sell Order"""
    data = request.get_json()
    stock_symbol = data.get('symbol')
    quantity = float(data.get('quantity'))
    trade_type = data.get('type').upper()
    
    if quantity <= 0:
        return jsonify({'error': 'Quantity must be positive'}), 400
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        settings = get_platform_settings(cursor)
        cursor.execute("SELECT * FROM stocks WHERE symbol = %s", (stock_symbol,))
        stock = cursor.fetchone()
        if not stock:
            return jsonify({'error': 'Stock not found'}), 404
        
        current_price = float(stock['current_price'])
        total_amount = quantity * current_price
        brokerage_percent = float(settings['brokerage_percent'])
        brokerage_fee = round(total_amount * (brokerage_percent / 100), 2)
        
        cursor.execute("SELECT balance FROM users WHERE id = %s", (session['user_id'],))
        user = cursor.fetchone()
        current_balance = float(user['balance'])
        
        realized_profit_loss = 0.0

        if trade_type == 'BUY':
            net_amount = total_amount + brokerage_fee
            if net_amount > current_balance:
                return jsonify({'error': 'Insufficient balance'}), 400
            cursor.execute("UPDATE users SET balance = balance - %s WHERE id = %s",
                (net_amount, session['user_id']))
            cursor.execute("""
                INSERT INTO holdings (user_id, stock_id, quantity, avg_buy_price)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                quantity = quantity + %s,
                avg_buy_price = (avg_buy_price * quantity + %s * %s) / (quantity + %s)
            """, (session['user_id'], stock['id'], quantity, current_price,
                quantity, current_price, quantity, quantity))

        elif trade_type == 'SELL':
            cursor.execute("""
                SELECT quantity, avg_buy_price FROM holdings
                WHERE user_id = %s AND stock_id = %s
            """, (session['user_id'], stock['id']))
            holding = cursor.fetchone()
            if not holding or float(holding['quantity']) < quantity:
                return jsonify({'error': 'Insufficient shares'}), 400

            avg_buy_price = float(holding['avg_buy_price'])
            realized_profit_loss = round((current_price - avg_buy_price) * quantity, 2)
            net_amount = total_amount - brokerage_fee
            
            cursor.execute("UPDATE users SET balance = balance + %s WHERE id = %s",
                (net_amount, session['user_id']))
            cursor.execute("""
                UPDATE holdings SET quantity = quantity - %s
                WHERE user_id = %s AND stock_id = %s
            """, (quantity, session['user_id'], stock['id']))
            cursor.execute("""
                DELETE FROM holdings WHERE user_id = %s AND stock_id = %s AND quantity <= 0.0001
            """, (session['user_id'], stock['id']))
        else:
            return jsonify({'error': 'Invalid trade type'}), 400

        try:
            cursor.execute("ALTER TABLE transactions ADD COLUMN IF NOT EXISTS brokerage_amount DECIMAL(12,2) DEFAULT 0.00")
        except Error:
            pass

        try:
            cursor.execute("ALTER TABLE transactions ADD COLUMN IF NOT EXISTS realized_profit_loss DECIMAL(12,2) DEFAULT NULL")
        except Error:
            pass
        
        try:
            cursor.execute("""
                INSERT INTO transactions
                (user_id, stock_id, transaction_type, quantity, price_per_unit, total_amount, brokerage_amount, realized_profit_loss)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (session['user_id'], stock['id'], trade_type, quantity, current_price, total_amount, brokerage_fee, realized_profit_loss if trade_type == 'SELL' else None))
        except Error:
            cursor.execute("""
                INSERT INTO transactions
                (user_id, stock_id, transaction_type, quantity, price_per_unit, total_amount)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (session['user_id'], stock['id'], trade_type, quantity, current_price, total_amount))
        
        conn.commit()
        
        cursor.execute("SELECT balance FROM users WHERE id = %s", (session['user_id'],))
        new_balance = float(cursor.fetchone()['balance'])
        
        return jsonify({
            'message': f'{trade_type} order executed successfully',
            'new_balance': round(new_balance, 2),
            'executed_price': round(current_price, 2),
            'total_amount': round(total_amount, 2),
            'net_amount': round(net_amount, 2),
            'brokerage_fee': round(brokerage_fee, 2),
            'brokerage_percent': round(brokerage_percent, 2),
            'realized_profit_loss': realized_profit_loss
        }), 200
    except Error as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

# ============= ADMIN-COMPATIBLE PORTFOLIO API =============
@app.route('/api/portfolio')
def get_portfolio_api():
    """Get portfolio - works for both users and admins"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        admin_view = request.args.get('admin_view', '0') == '1'
        user_id = request.args.get('user_id')
        
        if admin_view:
            if 'admin_id' not in session:
                return jsonify({'error': 'Admin authentication required'}), 401
            if not user_id:
                return jsonify({'error': 'user_id required for admin view'}), 400
            target_user_id = user_id
        else:
            if 'user_id' not in session:
                return jsonify({'error': 'User authentication required'}), 401
            target_user_id = session['user_id']
        
        cursor.execute("SELECT balance FROM users WHERE id = %s", (target_user_id,))
        user = cursor.fetchone()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        current_balance = float(user['balance'])
        
        query = """
            SELECT h.quantity, h.avg_buy_price, s.symbol, s.name, s.current_price,
                   (
                       SELECT MIN(t.transaction_date)
                       FROM transactions t
                       WHERE t.user_id = h.user_id
                         AND t.stock_id = h.stock_id
                         AND t.transaction_type = 'BUY'
                   ) as opened_at,
                   (
                       SELECT MAX(t.transaction_date)
                       FROM transactions t
                       WHERE t.user_id = h.user_id
                         AND t.stock_id = h.stock_id
                         AND t.transaction_type = 'BUY'
                   ) as last_buy_at
            FROM holdings h
            JOIN stocks s ON h.stock_id = s.id
            WHERE h.user_id = %s
        """
        cursor.execute(query, (target_user_id,))
        holdings = cursor.fetchall()
        
        portfolio = []
        total_value = 0
        for h in holdings:
            current_value = float(h['quantity']) * float(h['current_price'])
            total_value += current_value
            portfolio.append({
                'symbol': h['symbol'],
                'name': h['name'],
                'quantity': float(h['quantity']),
                'avg_buy_price': float(h['avg_buy_price']),
                'current_price': float(h['current_price']),
                'current_value': round(current_value, 2),
                'profit_loss': round(current_value - (float(h['quantity']) * float(h['avg_buy_price'])), 2),
                'opened_at': h['opened_at'].isoformat() if h.get('opened_at') else None,
                'last_buy_at': h['last_buy_at'].isoformat() if h.get('last_buy_at') else None
            })
        
        return jsonify({
            'holdings': portfolio,
            'total_value': round(total_value, 2),
            'balance': round(current_balance, 2)
        }), 200
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

# ============= ADMIN-COMPATIBLE ORDERS API =============
@app.route('/api/orders')
def get_orders_api():
    """Get orders - works for both users and admins"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        admin_view = request.args.get('admin_view', '0') == '1'
        user_id = request.args.get('user_id')
        
        if admin_view:
            if 'admin_id' not in session:
                return jsonify({'error': 'Admin authentication required'}), 401
            if not user_id:
                return jsonify({'error': 'user_id required for admin view'}), 400
            target_user_id = user_id
        else:
            if 'user_id' not in session:
                return jsonify({'error': 'User authentication required'}), 401
            target_user_id = session['user_id']
        
        try:
            cursor.execute("ALTER TABLE transactions ADD COLUMN IF NOT EXISTS realized_profit_loss DECIMAL(12,2) DEFAULT NULL")
        except Error:
            pass

        cursor.execute("""
            SELECT t.*, s.symbol, s.name, s.current_price,
                   CASE
                       WHEN t.transaction_type = 'SELL' THEN COALESCE(t.realized_profit_loss, 0)
                       ELSE ROUND((s.current_price - t.price_per_unit) * t.quantity, 2)
                   END AS profit_loss,
                   CASE
                       WHEN t.transaction_type = 'SELL' THEN 'Realized'
                       ELSE 'Live'
                   END AS profit_loss_type
            FROM transactions t
            JOIN stocks s ON t.stock_id = s.id
            WHERE t.user_id = %s
            ORDER BY t.transaction_date DESC
            LIMIT 100
        """, (target_user_id,))
        orders = cursor.fetchall()
        
        return jsonify(orders), 200
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

# ============= WATCHLIST APIs =============
@app.route('/api/watchlist/my')
@login_required
def get_my_watchlist():
    """Get user's personal watchlist with live prices."""
    my_watch_symbols = ['RELIANCE', 'TCS', 'INFY', 'AAPL', 'TSLA']
    stocks = fetch_live_stocks_from_db(my_watch_symbols)
    if stocks is None:
        return jsonify({'error': 'Database connection failed'}), 500

    stock_map = {stock['symbol']: stock for stock in stocks}
    ordered = [stock_map[symbol] for symbol in my_watch_symbols if symbol in stock_map]
    return jsonify(ordered), 200

@app.route('/api/watchlists')
@login_required
def get_all_watchlists():
    """Get all watchlists with live prices."""
    watchlist_specs = [
        {'id': 1, 'name': 'My Watchlist', 'symbols': ['RELIANCE', 'TCS', 'INFY', 'AAPL', 'TSLA']},
        {'id': 2, 'name': 'Tech Leaders', 'symbols': ['MSFT', 'GOOGL', 'NVDA', 'META', 'ORCL']},
        {'id': 3, 'name': 'Banking & Bluechips', 'symbols': ['HDFCBANK', 'ICICIBANK', 'SBIN', 'JPM', 'WMT']},
        {'id': 4, 'name': 'Growth Radar', 'symbols': ['AMZN', 'NFLX', 'PLTR', 'SUNPHARMA', 'NIFTY50']},
    ]
    all_symbols = []
    for watchlist in watchlist_specs:
        all_symbols.extend(watchlist['symbols'])

    live_stocks = fetch_live_stocks_from_db(list(dict.fromkeys(all_symbols)))
    if live_stocks is None:
        return jsonify({'error': 'Database connection failed'}), 500

    stock_map = {stock['symbol']: stock for stock in live_stocks}
    enriched_watchlists = []
    for watchlist in watchlist_specs:
        enriched_watchlists.append({
            'id': watchlist['id'],
            'name': watchlist['name'],
            'stocks': [stock_map[symbol] for symbol in watchlist['symbols'] if symbol in stock_map]
        })

    return jsonify(enriched_watchlists), 200

# ============= RUN APPLICATION =============
if __name__ == '__main__':
    os.makedirs('static/uploads/profiles', exist_ok=True)
    app.run(debug=True, port=5000)
