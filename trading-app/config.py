import os
from datetime import timedelta

class Config:
    # ===================================================================
    # 🔐 FLASK SECURITY SETTINGS
    # ===================================================================
    SECRET_KEY = os.environ.get('SECRET_KEY', 'trading-app-dev-key-2024-change-in-production')
    PERMANENT_SESSION_LIFETIME = timedelta(hours=24)
    
    # Session cookie security (enable in production)
    # SESSION_COOKIE_HTTPONLY = True
    # SESSION_COOKIE_SECURE = True  # Only with HTTPS
    # SESSION_COOKIE_SAMESITE = 'Lax'
    
    # ===================================================================
    # 🗄️ XAMPP MySQL DATABASE SETTINGS
    # ===================================================================
    MYSQL_HOST = os.environ.get('MYSQL_HOST', '127.0.0.1')
    MYSQL_PORT = int(os.environ.get('MYSQL_PORT', 3306))
    MYSQL_USER = os.environ.get('MYSQL_USER', 'root')
    MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', '')  # Empty for XAMPP default
    MYSQL_DB = os.environ.get('MYSQL_DB', 'trading_app')
    MYSQL_CURSORCLASS = 'DictCursor'
    
    # ===================================================================
    # 🔑 OAUTH CREDENTIALS (Social Login)
    # ===================================================================
    # Get these from respective developer consoles (instructions below)
    # For production: Use environment variables instead of hardcoding!
    
    # --- Google OAuth ---
    # Get from: https://console.cloud.google.com/
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', 'your-google-client-id')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', 'your-google-secret')
    GOOGLE_REDIRECT_URI = os.environ.get('GOOGLE_REDIRECT_URI', 'http://localhost:5000/auth/google/callback')
    
    # --- Apple Sign In ---
    # Get from: https://developer.apple.com/account/
    APPLE_CLIENT_ID = os.environ.get('APPLE_CLIENT_ID', 'your-apple-client-id')
    APPLE_CLIENT_SECRET = os.environ.get('APPLE_CLIENT_SECRET', 'your-apple-secret')
    APPLE_REDIRECT_URI = os.environ.get('APPLE_REDIRECT_URI', 'http://localhost:5000/auth/apple/callback')
    APPLE_TEAM_ID = os.environ.get('APPLE_TEAM_ID', 'your-apple-team-id')
    APPLE_KEY_ID = os.environ.get('APPLE_KEY_ID', 'your-apple-key-id')
    
    # --- GitHub OAuth ---
    # Get from: https://github.com/settings/developers
    GITHUB_CLIENT_ID = os.environ.get('GITHUB_CLIENT_ID', 'your-github-client-id')
    GITHUB_CLIENT_SECRET = os.environ.get('GITHUB_CLIENT_SECRET', 'your-github-secret')
    GITHUB_REDIRECT_URI = os.environ.get('GITHUB_REDIRECT_URI', 'http://localhost:5000/auth/github/callback')
    
    # ===================================================================
    # 🌐 APP SETTINGS
    # ===================================================================
    APP_NAME = 'TradeWise'
    DEBUG = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'  # Set to False in production
    
    # ===================================================================
    # 📧 EMAIL SETTINGS (Optional - for verification/password reset)
    # ===================================================================
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'True').lower() == 'true'
    MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL', 'False').lower() == 'true'
    
    # ===================================================================
    # 🔒 SECURITY SETTINGS
    # ===================================================================
    # Password requirements
    MIN_PASSWORD_LENGTH = 6
    REQUIRE_SPECIAL_CHAR = False  # Set to True for production
    
    # Rate limiting (requests per minute)
    RATELIMIT_ENABLED = os.environ.get('RATELIMIT_ENABLED', 'False').lower() == 'true'
    RATELIMIT_DEFAULT = "100 per minute"
    
    # ===================================================================
    # 📊 ANALYTICS & LOGGING
    # ===================================================================
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'DEBUG' if DEBUG else 'INFO')
    LOG_FILE = os.environ.get('LOG_FILE', 'trading_app.log')
