import mysql.connector
from dotenv import load_dotenv
import os

load_dotenv()

username = os.getenv("DBUSERNAME")
password = os.getenv("PASSWORD")
DB_host = os.getenv("HOST")
DATABASE_NAME = "agiletrack"#os.getenv("DATABASE")

print(DATABASE_NAME)
# load_dotenv()

# username = "admin"
# password = "password"
# DB_host = "agiletrackdb.chwc2ywyoj7b.us-east-1.rds.amazonaws.com"
# DATABASE_NAME = "agiletrackdb"

# Connect to MySQL server
conn = mysql.connector.connect(
            host= DB_host,
            user = username, 
            password = password, 
        )

# Create a cursor object
cursor = conn.cursor()

# Create the database
cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DATABASE_NAME}")

# Switch to the created database
cursor.execute(f"USE {DATABASE_NAME}")

# Create the boards table
cursor.execute("""
    CREATE TABLE IF NOT EXISTS boards (
    id INT NOT NULL AUTO_INCREMENT,
    columns JSON DEFAULT NULL,
    tasks JSON DEFAULT NULL,
    title VARCHAR(255) DEFAULT NULL,
    PRIMARY KEY (id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
""")

cursor.execute("""CREATE TABLE IF NOT EXISTS users (
                                id INT AUTO_INCREMENT PRIMARY KEY,
                                name VARCHAR(255),
                                email VARCHAR(255) UNIQUE NOT NULL,
                                password VARCHAR(255) NOT NULL
                            )""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_boards (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    board_id INT,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (board_id) REFERENCES boards(id)
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS board_owners (
    id INT AUTO_INCREMENT PRIMARY KEY,
    board_id INT,
    owner_id INT,
    FOREIGN KEY (board_id) REFERENCES boards(id),
    FOREIGN KEY (owner_id) REFERENCES users(id)
    )
""")



# Commit changes and close connection
conn.commit()
conn.close()
