import sqlite3

# Function to create connection to SQLite database
def create_connection():
    conn = sqlite3.connect('AgileTrack.db')
    return conn

# Function to erase all records from all tables
def erase_all_records():
    try:
        conn = create_connection()
        cursor = conn.cursor()
        
        # List all tables in the database
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        # Loop through each table and delete all records
        for table in tables:
            cursor.execute(f"DELETE FROM {table[0]}")
        
        conn.commit()
        cursor.close()
        conn.close()
        print("All records erased from all tables successfully.")
        
    except Exception as e:
        print(f"An error occurred: {str(e)}")

# Call the function to erase all records
erase_all_records()
