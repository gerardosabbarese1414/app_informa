import sqlite3
from pathlib import Path

DB_PATH = Path("informa.db")  # su Streamlit Cloud resta nel container (persistenza limitata)
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
conn.execute("PRAGMA foreign_keys = ON")
conn.row_factory = sqlite3.Row


def init_db():
    # users
    conn.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        created_at TEXT
    )
    """)

    # profile
    conn.execute("""
    CREATE TABLE IF NOT EXISTS user_profile (
        user_id INTEGER PRIMARY KEY,
        start_weight REAL,
        height_cm REAL,
        sex TEXT,
        age INTEGER,
        activity_level TEXT,
        goal_type TEXT,
        goal_weight REAL,
        goal_date TEXT,
        body_fat REAL,
        lean_mass REAL,
        updated_at TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)

    # day logs
    conn.execute("""
    CREATE TABLE IF NOT EXISTS day_logs (
        user_id INTEGER,
        date TEXT,
        morning_weight REAL,
        is_closed INTEGER DEFAULT 0,
        PRIMARY KEY(user_id, date),
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)

    # meals actual
    conn.execute("""
    CREATE TABLE IF NOT EXISTS meals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        date TEXT,
        time TEXT,
        description TEXT,
        calories REAL,
        raw_json TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)

    # workouts actual
    conn.execute("""
    CREATE TABLE IF NOT EXISTS workouts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        date TEXT,
        time TEXT,
        description TEXT,
        duration_min INTEGER,
        calories_burned REAL,
        raw_json TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)

    # daily summaries
    conn.execute("""
    CREATE TABLE IF NOT EXISTS daily_summaries (
        user_id INTEGER,
        date TEXT,
        calories_in REAL,
        rest_calories REAL,
        workout_calories REAL,
        calories_out REAL,
        net_calories REAL,
        PRIMARY KEY(user_id, date),
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)

    # planned events (calendar plan)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS planned_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        date TEXT,
        time TEXT,
        type TEXT,                 -- meal | workout
        title TEXT,
        expected_calories REAL,
        duration_min INTEGER,
        status TEXT DEFAULT 'planned',  -- planned | done
        notes TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)

    # weekly plan cache
    conn.execute("""
    CREATE TABLE IF NOT EXISTS weekly_plan (
        user_id INTEGER,
        iso_year INTEGER,
        iso_week INTEGER,
        content TEXT,
        created_at TEXT,
        PRIMARY KEY(user_id, iso_year, iso_week),
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)

    conn.commit()
    init_db()