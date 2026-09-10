import mysql.connector
from mysql.connector import Error

print("🔍 Testing Database Connection...")
print("=" * 50)

try:
    # Try connecting with new config
    connection = mysql.connector.connect(
        host='127.0.0.1',      # Changed from localhost
        port=3306,
        user='root',
        password='',           # Empty for XAMPP
        database='trading_app'
    )
    
    if connection.is_connected():
        print("✅ SUCCESS! Database connected!")
        print(f"📊 Connected to: {connection.database}")
        print(f"🖥️  Server version: {connection.server_version}")
        
        # Test if admins table exists
        cursor = connection.cursor()
        cursor.execute("SHOW TABLES LIKE 'admins'")
        result = cursor.fetchone()
        
        if result:
            print("✅ Table 'admins' exists!")
            
            # Check if admin user exists
            cursor.execute("SELECT username FROM admins")
            admins = cursor.fetchall()
            if admins:
                print(f"✅ Admin users found: {[a[0] for a in admins]}")
            else:
                print("⚠️  No admin users found! Run the INSERT SQL.")
        else:
            print("❌ Table 'admins' NOT FOUND!")
            print("👉 Run the CREATE TABLE SQL from instructions.")
        
        cursor.close()
        connection.close()
        
    else:
        print("❌ Connection object exists but not connected")
        
except Error as e:
    print("❌ Database Error:", e)
    print("\n🔧 Troubleshooting Steps:")
    print("1. Open XAMPP Control Panel")
    print("2. Make sure MySQL shows 'Running' (green)")
    print("3. Open http://localhost/phpmyadmin")
    print("4. Check if 'trading_app' database exists")
    print("5. If MySQL has a password, update MYSQL_PASSWORD in config.py")