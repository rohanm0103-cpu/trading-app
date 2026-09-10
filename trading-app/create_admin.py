from werkzeug.security import generate_password_hash
import mysql.connector
from mysql.connector import Error

print("🔐 Creating Admin Account")
print("=" * 50)

# Admin credentials
username = "admin"
password = "admin123"

# Generate password hash
print(f"🔑 Creating admin: {username}")
print(f"🔑 Password: {password}")
password_hash = generate_password_hash(password)

# Connect to database
try:
    conn = mysql.connector.connect(
        host='127.0.0.1',
        user='root',
        password='',
        database='trading_app'
    )
    
    cursor = conn.cursor()
    
    # Create admins table if not exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(50) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    print("✅ Table 'admins' ready")
    
    # Delete existing admin (if any)
    cursor.execute("DELETE FROM admins WHERE username = %s", (username,))
    conn.commit()
    
    # Insert new admin
    cursor.execute(
        "INSERT INTO admins (username, password_hash) VALUES (%s, %s)",
        (username, password_hash)
    )
    conn.commit()
    
    print("\n" + "=" * 50)
    print("✅ SUCCESS! Admin account created!")
    print("=" * 50)
    print(f"👤 Username: {username}")
    print(f"🔑 Password: {password}")
    print("\n📝 Now try logging in at:")
    print("   http://localhost:5000/login/admin")
    print("=" * 50)
    
    cursor.close()
    conn.close()
    
except Error as e:
    print(f"\n❌ Database Error: {e}")
    print("\n🔧 Make sure:")
    print("1. XAMPP MySQL is running")
    print("2. Database 'trading_app' exists")
    input("\nPress Enter to exit...")