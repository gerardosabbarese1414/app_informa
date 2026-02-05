import bcrypt
from database import conn

def register(email, password):
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
    conn.execute("INSERT INTO users (email, password) VALUES (?,?)", (email, hashed))
    conn.commit()

def login(email, password):
    row = conn.execute("SELECT id, password FROM users WHERE email=?", (email,)).fetchone()
    if row and bcrypt.checkpw(password.encode(), row[1]):
        return row[0]
    return None