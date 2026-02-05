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
    CREATE TABLE IF NOT EXISTS day_logs (
        user_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        morning_weight REAL,
        is_closed INTEGER DEFAULT 0,
        notes TEXT,
        PRIMARY KEY (user_id, date)
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS meals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        time TEXT,
        description TEXT,
        calories REAL,
        raw_json TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS workouts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        time TEXT,
        activity TEXT,
        duration_min INTEGER,
        calories_burned REAL
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS daily_summaries (
        user_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        calories_in REAL,
        calories_out REAL,
        net_calories REAL,
        PRIMARY KEY (user_id, date)
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS weekly_plan (
        user_id INTEGER NOT NULL,
        iso_year INTEGER NOT NULL,
        iso_week INTEGER NOT NULL,
        content TEXT,
        created_at TEXT,
        PRIMARY KEY (user_id, iso_year, iso_week)
    )
    """)

    c.execute("CREATE INDEX IF NOT EXISTS idx_meals_user_date ON meals(user_id, date)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_workouts_user_date ON workouts(user_id, date)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_daylogs_user_date ON day_logs(user_id, date)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_summ_user_date ON daily_summaries(user_id, date)")

    conn.commit()

init_db()