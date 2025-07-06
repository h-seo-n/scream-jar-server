from flask import Flask, jsonify, request

# import sqlite3
import psycopg2
import os
from psycopg2 import errors

from flask_cors import CORS
from datetime import datetime

import click
import bcrypt

app = Flask(__name__)
CORS(app)

# path to SQLite database file
# DB_FILE = "appdata.db"
DB_URL = os.environ.get("DATABASE_URL")  # set this in Render

# helper function to execute queries
# def query_db(query, args=(), fetchone=False, fetchall=False, commit=False):
#     with sqlite3.connect(DB_FILE) as conn:
#         conn.row_factory = sqlite3.Row
#         cursor = conn.cursor()
#         cursor.execute(query,args)
#         if commit:
#             conn.commit()
#         if fetchone:
#             return cursor.fetchone()
#         if fetchall:
#             return cursor.fetchall()
#         return None

def query_db(query, args=(), fetchone=False, fetchall=False, commit=False):
    conn = psycopg2.connect(DB_URL)
    cursor = conn.cursor()
    cursor.execute(query, args)
    result = None
    if fetchone:
        row = cursor.fetchone()
        if row:
            colnames = [desc[0] for desc in cursor.description]
            result = dict(zip(colnames, row))
    elif fetchall:
        rows = cursor.fetchall()
        colnames = [desc[0] for desc in cursor.description]
        result = [dict(zip(colnames, row)) for row in rows]
    if commit:
        conn.commit()
    cursor.close()
    conn.close()
    return result



# API endpoints
# 1. initialize dataase
@app.route('/initialize', methods=['POST'])
def initialize_database():
    try:
        conn = psycopg2.connect(DB_URL)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT NOT NULL,
                password TEXT,
                wallcolor TEXT,
                friendlist TEXT DEFAULT ''
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS screams (
                id SERIAL PRIMARY KEY,
                userid TEXT NOT NULL,
                categoryindex INTEGER,
                content TEXT,
                screamdate TEXT,
                FOREIGN KEY (userid) REFERENCES users(id) ON DELETE CASCADE
            );
        """)
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"message": "PostgreSQL tables initialized"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# def initialize_database():
#     try:
#         with sqlite3.connect(DB_FILE) as conn:
#             cursor = conn.cursor()
#             cursor.executescript("""
#             CREATE TABLE IF NOT EXISTS users (
#                 id TEXT PRIMARY KEY,
#                 username TEXT NOT NULL,
#                 password TEXT,
#                 wallColor TEXT,
#                 friendList TEXT DEFAULT ''
#             );
                                 
#             CREATE TABLE IF NOT EXISTS screams (
#                 id INTEGER PRIMARY KEY AUTOINCREMENT,
#                 userID TEXT NOT NULL,
#                 categoryIndex INTEGER,
#                 content TEXT,
#                 screamDate TEXT,
#                 FOREIGN KEY (userID) REFERENCES users(id) ON DELETE CASCADE
#             );
#             """)
#         return jsonify({"message": "Database initialized"}), 200
#     except Exception as e:
#         return jsonify({"error": str(e)}), 500

# login
@app.route('/login', methods=['POST'])
def login():
    data = request.json
    id = data.get('id')
    password = data.get('password')

    if not id or not password:
        return jsonify({"error": "Missing Credentials"}), 400

    user = query_db("SELECT * FROM users WHERE id = %s", (id,), fetchone = True)

    if user and bcrypt.checkpw(password.encode(), user["password"].encode()):
        return jsonify({"message": "Login successful"}), 200
    else:
        return jsonify({"error": "Invalid ID or password"}), 401



# 2. save user (friendlist not updated because it has other func for that purpose)
@app.route('/users', methods=['POST'])
def save_user():
    data = request.json
    id = data['id']
    username = data['username']
    wallColor = data['wallColor']
    password = data['password']
    # no friendlist!

    hashed_pw = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    try:
        query_db("""
        INSERT INTO users (id, username, password, wallcolor, friendlist)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT(id) DO UPDATE SET
            username = excluded.username,
            password = excluded.password,
            wallColor = excluded.wallcolor,
            friendList = COALESCE(users.friendlist, excluded.friendlist)
        """, (id, username, hashed_pw, wallColor, ""), commit=True)
        return jsonify({"message": "User saved successfully"}), 200
    except psycopg2.errors.UniqueViolation:
        return jsonify({"error": "id already exists"}), 400
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    return jsonify({"message": "user saved"}), 200

# 3. Load user
@app.route('/users/<user_id>', methods=['GET'])
def load_user(user_id):
    user = query_db("SELECT * FROM users WHERE id = %s", (user_id,), fetchone = True)
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify(dict(user)), 200


# 4. Check if User Exists
@app.route('/users/<user_id>/exists', methods=['GET'])
def user_exists(user_id):
    count = query_db("SELECT COUNT(*) AS count FROM users WHERE id = %s", (user_id,), fetchone=True)
    exists = count["count"] > 0
    return jsonify({"exists": exists}), 200


# 5. Save Scream
@app.route('/screams', methods=['POST'])
def save_scream():
    data = request.json
    userID = data['userID']
    categoryIndex = data['categoryIndex']
    content = data['content']
    screamDate = data['screamDate']

    try:
        query_db("""
        INSERT INTO screams (userid, categoryindex, content, screamdate)
        VALUES (%s, %s, %s, %s)
        """, (userID, categoryIndex, content, screamDate), commit=True)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    return jsonify({"message": "Scream saved"}), 200



# 6. Load Screams
@app.route('/screams/<user_id>', methods=['GET'])
def load_screams(user_id):
    screams = query_db("""
    SELECT id, categoryindex, content, screamdate FROM screams WHERE userid = %s
    """, (user_id,), fetchall=True)

    return jsonify([dict(scream) for scream in screams]), 200


# 7. Get Username by User ID
@app.route('/users/<user_id>/username', methods=['GET'])
def get_username_by_user_id(user_id):
    username = query_db("SELECT username FROM users WHERE id = %s", (user_id,), fetchone=True)
    if not username:
        return jsonify({"error": "User not found"}), 404
    return jsonify({"username": username['username']}), 200


# 8. add friend
@app.route('/add-friend', methods=['POST'])
def add_friend():
    data = request.get_json()
    myUserID = data.get('myUserID')
    friendUserID = data.get('friendUserID')

    if not myUserID or not friendUserID:
        return jsonify({"error": "Missing data"}), 400

    user = query_db("SELECT friendlist FROM users WHERE id = %s", (myUserID,), fetchone = True)
    if user is None:
        return jsonify({"error": "User not found"}), 404
    
    friend_list = user["friendlist"].split(',') if user["friendlist"] else []
    if friendUserID not in friend_list:
        friend_list.append(friendUserID)
        new_friend_list = ','.join(friend_list)

        query_db("UPDATE users SET friendlist = %s WHERE id = %s", (new_friend_list, myUserID), commit=True)
        return jsonify({"message": "Freind added successfully"}), 200
    else:
        return jsonify({"message": "Friend already exists"}), 200



# 9. delete friend
@app.route('/delete-friend', methods=['DELETE'])
def delete_friend():
    data = request.get_json()
    myUserID = data.get('myUserID')
    friendUserID = data.get('friendUserID')

    if not myUserID or not friendUserID:
        return jsonify({"error": "Missing data"}), 400

    user = query_db("SELECT friendlist FROM users WHERE id = %s", (myUserID,), fetchone=True)
    if user is None:
        return jsonify({"error": "User not found"}), 404
    
    friend_list = user[0].split(',') if user[0] else[]
    if friendUserID in friend_list:
        friend_list.remove(friendUserID)
        new_friend_list = ','.join(friend_list)

        query_db("UPDATE users SET friendlist = %s WHERE id = %s", (new_friend_list, myUserID), commit=True)
        return jsonify({"message": "Friend deleted Successfully"}), 200
    else:
        return jsonify({"message": "Friend not in list"}), 404


# 10. search for users (to add friend)    
@app.route('/friend-search', methods=['GET'])
def friend_search():
    userID = request.args.get('id')
    if not userID:
        return jsonify({"error": "UserID not provided"})
    
    user = query_db("""
    SELECT id, username, wallcolor, friendlist FROM users WHERE id = %s
    """, (userID,), fetchone=True)

    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify(user), 200


# 11. (added) for save function that isn't for register
@app.route('/users/no-password', methods=['POST'])
def save_user_no_password():
    data = request.json
    id = data['id']
    username = data['username']
    wallColor = data['wallColor']

    try:
        query_db("""
        INSERT INTO users (id, username, wallcolor)
        VALUES (%s, %s, %s)
        ON CONFLICT(id) DO UPDATE SET
            username = EXCLUDED.username,
            wallColor = EXCLUDED.wallcolor
        """, (id, username, wallColor), commit=True)

        return jsonify({"message": "User saved (no password)"}), 200
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    #    app.run(debug=True)
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
