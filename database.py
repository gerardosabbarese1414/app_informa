import sqlite3

conn = sqlite3.connect("fitness.db", check_same_thread=False)
c = conn.cursor()

c.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE,
    password BLOB
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS weight (
    user_id INTEGER,
    date TEXT,
    weight REAL
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS workouts (
    user_id INTEGER,
    date TEXT,
    activity TEXT,
    duration INTEGER
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS meals (
    user_id INTEGER,
    date TEXT,
    description TEXT,
    calories REAL
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS weekly_plan (
    user_id INTEGER,
    week TEXT,
    content TEXT
)
""")

conn.commit()