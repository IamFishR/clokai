#!/usr/bin/env python3

import pymysql
from config import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME

def setup_database():
    # Read schema file
    with open('database/schema.sql', 'r') as f:
        schema_sql = f.read()
    
    # Connect to MySQL
    connection = pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD
    )
    
    try:
        with connection.cursor() as cursor:
            # Split and execute each statement
            statements = [stmt.strip() for stmt in schema_sql.split(';') if stmt.strip()]
            
            for statement in statements:
                if statement and not statement.startswith('--'):
                    print(f"Executing: {statement[:50]}...")
                    try:
                        cursor.execute(statement)
                        print("Success!")
                    except pymysql.err.OperationalError as e:
                        if "already exists" in str(e):
                            print(f"Skipping (already exists): {e}")
                        else:
                            raise
        
        connection.commit()
        print("Database schema setup completed successfully!")
        
        # Test the setup
        connection.select_db(DB_NAME)
        with connection.cursor() as cursor:
            cursor.execute("SHOW TABLES")
            tables = cursor.fetchall()
            print(f"Created tables: {[table[0] for table in tables]}")
            
    finally:
        connection.close()

if __name__ == "__main__":
    setup_database()