import os
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import mysql.connector
import jwt
import datetime
import mysql.connector
from functools import wraps
import hashlib
from flask_mail import Mail, Message
from flask import Flask, render_template, request, redirect, url_for, flash
import smtplib
from email.message import EmailMessage
import boto3


app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})
load_dotenv()

# MySQL configurations
username = os.getenv("DBUSERNAME")
password = os.getenv("PASSWORD")
host = os.getenv("HOST")
database_name = os.getenv("DATABASE")

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True
app.config['MAIL_USERNAME'] = 'agiletrack.service@gmail.com'
app.config['MAIL_PASSWORD'] = 'dtzw tuaq ejtm qkqd'

mail = Mail(app)

def create_connection():
    return mysql.connector.connect(
        host=host,
        user=username,
        passwd=password,
        database=database_name
    )

# Create 'boards' table if not exists
create_boards_table_query = """
CREATE TABLE IF NOT EXISTS boards (
    id INT AUTO_INCREMENT PRIMARY KEY,
    state JSON
)
"""
conn = create_connection()
cursor = conn.cursor()
cursor.execute(create_boards_table_query)
conn.commit()
cursor.close()
conn.close()

# Secret key for JWT
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY")

# Middleware to verify JWT token
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None

        # Check if token is present in the headers
        if 'Authorization' in request.headers:
            token = request.headers['Authorization'].split(" ")[1]

        if not token:
            return jsonify({'message': 'Token is missing'}), 401

        try:
            # Decode and verify the token
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            user_id = data["user_id"]
            email = data['email']
            conn = create_connection()
            cursor = conn.cursor()

            # Fetch user from the database
            cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
            current_user = cursor.fetchone()
            return f(current_user, *args, **kwargs)

        except jwt.ExpiredSignatureError:
            return jsonify({'message': 'Token has expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'message': 'Invalid token'}), 401
    return decorated

@app.route('/protected', methods=['GET'])
@token_required
def protected_route(current_user):
    return jsonify({'message': 'This is a protected route!'})

# Route for user signup
@app.route('/signup', methods=['POST'])
def signup():
    data = request.json
    name = data['name']
    email = data['email']
    password = data['password']

    # Hash the password using SHA-256
    hashed_password = hashlib.sha256(password.encode()).hexdigest()

    try:
        conn = create_connection()
        cursor = conn.cursor()
        # Check if name or email already exists
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        existing_user = cursor.fetchone()
        if existing_user:
            return jsonify({'message': 'Email already exists'}), 400

        # Insert new user into the database
        cursor.execute("INSERT INTO users (name, email, password) VALUES (%s, %s, %s)", (name, email, hashed_password))
        user_id = cursor.lastrowid

        # Create a new board for the user with specified data
        columns_data = '[{"id": "todo", "title": "TO DO"}, {"id": "progress", "title": "In Progress"}, {"id": "done", "title": "Done"}]'
        tasks_data = '[{"columnId": "todo", "content": "New Task 1", "id": "14"}]'
        board_title = 'My Board'
        
        cursor.execute("INSERT INTO boards (columns, tasks, title) VALUES (%s, %s, %s)", (columns_data, tasks_data, board_title))
        board_id = cursor.lastrowid

        # Associate the user with the board
        cursor.execute("INSERT INTO user_boards (user_id, board_id) VALUES (%s, %s)", (user_id, board_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        expiration_time = datetime.datetime.utcnow() + datetime.timedelta(days=120)  # 4 months

        # Generate JWT token
        token = jwt.encode({'user_id': user_id,'email': email, 'exp': expiration_time}, app.config['SECRET_KEY'])

        return jsonify({'message': 'User created successfully', 'token': token}), 201

    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Route for user login
@app.route('/login', methods=['POST'])
def login():
    data = request.json
    if not data or 'email' not in data or 'password' not in data:
        return jsonify({'message': 'Invalid email or password format'}), 400

    email = data['email']
    password = data['password']
    conn = create_connection()
    cursor = conn.cursor()
    # Fetch user from the database
    cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    if not user or user[3] != hashlib.sha256(password.encode()).hexdigest():
        return jsonify({'message': 'Invalid email or password'}), 401
    expiration_time = datetime.datetime.utcnow() + datetime.timedelta(days=120)  # 4 months

    # Generate JWT token
    token = jwt.encode({'user_id': user[0],'email': user[2], 'exp': expiration_time}, app.config['SECRET_KEY'])

    return jsonify({'token': token}), 200


@app.route("/update_board", methods=["PUT"])
@token_required
def update_board(current_user):
    data = request.json
    board_id = data.get("boardId")
    board = data.get("board")
    board_title = data.get("boardTitle")
    if board_title == None:
        update_query = "UPDATE boards SET columns = %s, tasks = %s WHERE id = %s"
        conn = create_connection()
        cursor = conn.cursor()
        cursor.execute(update_query, (json.dumps(board['columns']), json.dumps(board['tasks']), board_id))
    else:
        update_query = "UPDATE boards SET columns = %s, tasks = %s, title = %s WHERE id = %s"
        conn = create_connection()
        cursor = conn.cursor()
        cursor.execute(update_query, (json.dumps(board['columns']), json.dumps(board['tasks']), board_title, board_id))

        
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"message": "Board updated successfully"})


@app.route("/get_boards", methods=["GET"])
@token_required
def get_boards(current_user):
    conn = create_connection()
    cursor = conn.cursor()

    try:
        # Retrieve boards owned by the user
        cursor.execute("""
            SELECT b.id, b.columns, b.tasks, b.title
            FROM boards b
            INNER JOIN board_owners bo ON b.id = bo.board_id
            WHERE bo.owner_id = %s
        """, (current_user[0],))
        owned_boards = cursor.fetchall()

        # Retrieve boards shared with the user
        cursor.execute("""
            SELECT b.id, b.columns, b.tasks, b.title
            FROM boards b
            INNER JOIN user_boards ub ON b.id = ub.board_id
            WHERE ub.user_id = %s AND b.id NOT IN (
                SELECT bo.board_id
                FROM board_owners bo
                WHERE bo.owner_id = %s
            )
        """, (current_user[0], current_user[0]))
        shared_boards = cursor.fetchall()

        boards = {
            "owned_boards": [],
            "shared_boards": []
        }

        for board in owned_boards:
            boards["owned_boards"].append({
                "id": board[0],
                "columns": json.loads(board[1]),
                "tasks": json.loads(board[2]),
                "title": board[3]
            })

        for board in shared_boards:
            boards["shared_boards"].append({
                "id": board[0],
                "columns": json.loads(board[1]),
                "tasks": json.loads(board[2]),
                "title": board[3]
            })

        return jsonify(boards)

    except Exception as e:
        return jsonify({"message": str(e)}), 500

    finally:
        cursor.close()
        conn.close()

@app.route("/get_user_details", methods=["GET"])
@token_required
def get_user_details(current_user):
    conn = create_connection()
    cursor = conn.cursor()

    try:
        # Retrieve user details
        cursor.execute("""
            SELECT id, name
            FROM users
            WHERE id = %s
        """, (current_user[0],))
        user_details = cursor.fetchone()
        print(user_details)
        if user_details:
            user = {
                "id": user_details[0],
                "name": user_details[1]
            }
            return jsonify(user)
        else:
            return jsonify({"message": "User not found"}), 404

    except Exception as e:
        return jsonify({"message": str(e)}), 500

    finally:
        cursor.close()
        conn.close()

@app.route("/add_board", methods=["POST"])
@token_required
def add_board(current_user):

    conn = create_connection()
    cursor = conn.cursor()

    # Create a new board for the user with specified data
    columns_data = json.dumps([{"id": "todo", "title": "TO DO"}, {"id": "progress", "title": "In Progress"}, {"id": "done", "title": "Done"}])
    tasks_data = json.dumps([{"columnId": "todo", "content": "New Task 1", "id": "14"}])
    board_title = 'My Board'

    cursor.execute("INSERT INTO boards (columns, tasks, title) VALUES (%s, %s, %s)", (columns_data, tasks_data, board_title))
    board_id = cursor.lastrowid

    # Map current authenticated user with the newly created board
    cursor.execute("INSERT INTO board_owners (owner_id, board_id) VALUES (%s, %s)", (current_user[0], board_id))

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"message": "Board added successfully"})


@app.route("/share_board", methods=["POST"])
@token_required
def share_board(current_user):
    data = request.json
    board_id = data.get("board_id")
    to_email = data.get("invitee_email")
    from_name = current_user[1]
    from_email = current_user[2]

    if not board_id or not to_email:
        return jsonify({"message": "Missing required fields"}), 400

    conn = create_connection()
    cursor = conn.cursor()

    # Check if the board exists
    cursor.execute("SELECT * FROM boards WHERE id = %s", (board_id,))
    board = cursor.fetchone()
    board_title = board[3]

    if not board:
        return jsonify({"message": "Board not found"}), 404

    # Fetch user ID from email
    cursor.execute("SELECT id FROM users WHERE email = %s", (to_email,))
    user = cursor.fetchone()
    if not user:
        return jsonify({"message": "User not found"}), 404

    # Check if the board is already shared with the user
    cursor.execute("SELECT * FROM user_boards WHERE board_id = %s AND user_id = %s", (board_id, user[0]))
    shared_board = cursor.fetchone()
    if shared_board:
        return jsonify({"message": "Board is already shared with this user"}), 400

    conn.commit()
    cursor.close()
    conn.close()
    # Share the board with the user
    cursor.execute("INSERT INTO user_boards (board_id, user_id) VALUES (%s, %s)", (board_id, user[0]))
    return send_email_from_backend(to_email, from_email, from_name, board_title)

    # return jsonify({"message": "Board shared successfully"}), 200

def send_email_from_backend(to_email, from_email, from_name, board_title):
    recipient = to_email
    subject = "Invitation from " + str(from_name) + " to join in " + str(board_title)
    body = f"""Hi,

I'm inviting you to join our Agile Track board titled "{board_title}". Your insights would be invaluable to our team.

To join the board, login Aglie Track Now.

Looking forward to having you onboard!

Best regards,
{from_name}
    """
    if not recipient or not subject or not body:
        return jsonify({'error': 'Missing required fields'}), 400

    try:
        # Initialize boto3 client for AWS Lambda
        session = boto3.Session(profile_name='lab')
        lambda_client = session.client('lambda', region_name='us-east-1')

        # Payload to be passed to the Lambda function
        payload = {
            "recipient": to_email,
            "subject": subject,
            "body": body
        }

        # Invoke the Lambda function
        response = lambda_client.invoke(
            FunctionName='arn:aws:lambda:us-east-1:730335289956:function:mailSender',
            InvocationType='RequestResponse',  # Synchronous invocation
            Payload=json.dumps(payload)
        )
        print(response)

        # Check the response
        response_payload = response['Payload'].read()
        response_code = response['StatusCode']

        if response_code == 200:
            return jsonify({'message': 'Email sent successfully'}), 200
        else:
            return jsonify({'error': response_payload.decode()}), response_code

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/send_email', methods=['POST'])
def send_email():
    data = request.json
    recipient = data.get('recipient')
    subject = data.get('subject')
    body = data.get('body')
    if not recipient or not subject or not body:
        return jsonify({'error': 'Missing required fields'}), 400

    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = 'agiletrack.service@gmail.com'
    msg['To'] = recipient
    msg.set_content(body)

    try:
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login('agiletrack.service@gmail.com', 'dtzw tuaq ejtm qkqd')
        server.send_message(msg)
        server.quit()
        return jsonify({'message': 'Email sent successfully'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True)
