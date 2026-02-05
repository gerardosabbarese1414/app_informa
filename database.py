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
CREATE TABLE IF NOT EXISTS day_logs (
    user_id INTEGER,
    date TEXT,
    morning_weight REAL,
    is_closed INTEGER DEFAULT 0,
    notes TEXT,
    PRIMARY KEY (user_id, date)
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS meals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    date TEXT,
    time TEXT,
    description TEXT,
    calories REAL,
    raw_json TEXT
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS workouts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    date TEXT,
    time TEXT,
    activity TEXT,
    duration_min INTEGER,
    calories_burned REAL
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS daily_summaries (
    user_id INTEGER,
    date TEXT,
    calories_in REAL,
    calories_out REAL,
    net_calories REAL,
    PRIMARY KEY (user_id, date)
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS weekly_plan (
    user_id INTEGER,
    iso_year INTEGER,
    iso_week INTEGER,
    content TEXT,
    created_at TEXT,
    PRIMARY KEY (user_id, iso_year, iso_week)
)
""")

conn.commit()