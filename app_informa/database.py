import os
import sqlite3

DB_PATH = os.getenv("DB_PATH", "app.db")

conn = sqlite3.connect(DB_PATH, check_same_thread=False)
conn.execute("PRAGMA foreign_keys = ON")


def init_db():
    conn.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """)

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

    conn.execute("""
    CREATE TABLE IF NOT EXISTS day_logs (
        user_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        morning_weight REAL,
        is_closed INTEGER DEFAULT 0,
        PRIMARY KEY(user_id, date),
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS meals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        time TEXT,
        description TEXT,
        calories REAL,
        raw_json TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_meals_user_date ON meals(user_id, date)")

    conn.execute("""
    CREATE TABLE IF NOT EXISTS workouts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        time TEXT,
        description TEXT,
        duration_min INTEGER,
        calories_burned REAL,
        raw_json TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_workouts_user_date ON workouts(user_id, date)")

    conn.execute("""
    CREATE TABLE IF NOT EXISTS daily_summaries (
        user_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        calories_in REAL,
        rest_calories REAL,
        workout_calories REAL,
        calories_out REAL,
        net_calories REAL,
        PRIMARY KEY(user_id, date),
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS planned_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        time TEXT,
        type TEXT NOT NULL,              -- 'meal' | 'workout'
        title TEXT NOT NULL,
        expected_calories REAL,
        duration_min INTEGER,
        status TEXT DEFAULT 'planned',   -- planned | done | skipped | modified
        notes TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_planned_user_date ON planned_events(user_id, date)")

    conn.execute("""
    CREATE TABLE IF NOT EXISTS weekly_plan (
        user_id INTEGER NOT NULL,
        iso_year INTEGER NOT NULL,
        iso_week INTEGER NOT NULL,
        content TEXT NOT NULL,
        created_at TEXT NOT NULL,
        PRIMARY KEY (user_id, iso_year, iso_week),
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)

    conn.commit()


init_db()