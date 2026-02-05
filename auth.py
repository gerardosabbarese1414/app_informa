import bcrypt
from database import conn

def register(email, password):
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
    conn.execute(
        "INSERT INTO users (email, password) VALUES (?,?)",
        (email, hashed)
    )
    conn.commit()

def login(email, password):
    user = conn.execute(
        "SELECT id, password FROM users WHERE email=?",
        (email,)
    ).fetchone()

    if user and bcrypt.checkpw(password.encode(), user[1]):
        return user[0]
    return None