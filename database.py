import sqlite3

DB_PATH = "fitness.db"
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
conn.execute("PRAGMA foreign_keys = ON;")

def init_db():
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password BLOB NOT NULL
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS user_profile (
        user_id INTEGER PRIMARY KEY,
        start_weight REAL,
        height_cm REAL,
        sex TEXT,
        age INTEGER,
        body_fat_pct REAL,
        lean_mass_kg REAL,
        activity_level TEXT,
        goal_type TEXT,
        goal_weight REAL,
        goal_date TEXT,
        updated_at TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS day_logs (
        user_id INTEGER,
        date TEXT,
        morning_weight REAL,
        is_closed INTEGER DEFAULT 0,
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
        description TEXT,
        calories_burned REAL,
        raw_json TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS daily_summaries (
        user_id INTEGER,
        date TEXT,
        calories_in REAL,
        calories_out REAL,
        rest_calories REAL,
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

init_db()