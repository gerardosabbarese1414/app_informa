import os
import sqlite3

DB_PATH = os.getenv("DB_PATH", "app.db")
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
conn.execute("PRAGMA foreign_keys=ON")


def _table_exists(name: str) -> bool:
    r = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone()
    return bool(r)


def _col_exists(table: str, col: str) -> bool:
    try:
        cols = conn.execute(f"PRAGMA table_info({table})").fetchall()
        return any(c[1] == col for c in cols)
    except Exception:
        return False


def _add_col(table: str, coldef: str):
    conn.execute(f"ALTER TABLE {table} ADD COLUMN {coldef}")


def init_db():
    # USERS
    conn.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """)

    # PROFILE
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

    # DAY LOGS
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

    # MEALS
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

    # WORKOUTS
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

    # DAILY SUMMARIES
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

    # PLANNED EVENTS
    conn.execute("""
    CREATE TABLE IF NOT EXISTS planned_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        time TEXT,
        type TEXT NOT NULL,              -- meal | workout
        title TEXT NOT NULL,
        expected_calories REAL,
        duration_min INTEGER,
        status TEXT DEFAULT 'planned',   -- planned | done | skipped | modified
        notes TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_planned_user_date ON planned_events(user_id, date)")

    # WEEKLY PLAN CACHE
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

    # --- Lightweight migrations (if you had older tables) ---
    # planned_events missing cols?
    if _table_exists("planned_events"):
        if not _col_exists("planned_events", "status"):
            _add_col("planned_events", "status TEXT DEFAULT 'planned'")
        if not _col_exists("planned_events", "notes"):
            _add_col("planned_events", "notes TEXT")
        conn.commit()

    if _table_exists("user_profile"):
        for coldef, col in [
            ("body_fat REAL", "body_fat"),
            ("lean_mass REAL", "lean_mass"),
            ("updated_at TEXT", "updated_at"),
        ]:
            if not _col_exists("user_profile", col):
                _add_col("user_profile", coldef)
        conn.commit()


init_db()