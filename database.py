import sqlite3

DB_PATH = "fitness.db"
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
conn.execute("PRAGMA foreign_keys = ON;")


def _table_exists(name: str) -> bool:
    r = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (name,)
    ).fetchone()
    return r is not None


def _cols(name: str) -> list[str]:
    if not _table_exists(name):
        return []
    rows = conn.execute(f"PRAGMA table_info({name})").fetchall()
    return [r[1] for r in rows]


def _create_tables():
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
        user_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        morning_weight REAL,
        is_closed INTEGER DEFAULT 0,
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
        description TEXT,
        duration_min INTEGER,
        calories_burned REAL,
        raw_json TEXT
    )
    """)

    # ✅ Schema “nuovo” atteso dal codice
    c.execute("""
    CREATE TABLE IF NOT EXISTS daily_summaries (
        user_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        calories_in REAL,
        rest_calories REAL,
        workout_calories REAL,
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

    # indici
    c.execute("CREATE INDEX IF NOT EXISTS idx_meals_user_date ON meals(user_id, date)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_workouts_user_date ON workouts(user_id, date)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_summ_user_date ON daily_summaries(user_id, date)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_daylogs_user_date ON day_logs(user_id, date)")

    conn.commit()


def _migrate_daily_summaries_if_needed():
    """
    Se esiste daily_summaries con schema vecchio (es. colonne diverse),
    la migra a schema nuovo senza perdere i dati “compatibili”.
    """
    if not _table_exists("daily_summaries"):
        return

    current = set(_cols("daily_summaries"))
    required = {"user_id", "date", "calories_in", "rest_calories", "workout_calories", "calories_out", "net_calories"}

    # Se già ok, niente da fare
    if required.issubset(current):
        return

    # Creiamo una tabella nuova con schema corretto
    conn.execute("""
    CREATE TABLE IF NOT EXISTS daily_summaries_new (
        user_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        calories_in REAL,
        rest_calories REAL,
        workout_calories REAL,
        calories_out REAL,
        net_calories REAL,
        PRIMARY KEY (user_id, date)
    )
    """)

    # Prepara query di copia “intelligente”
    # Mappiamo vecchie colonne se presenti: net -> net_calories
    cols_old = _cols("daily_summaries")
    has_net = "net" in cols_old and "net_calories" not in cols_old

    # Costruzione SELECT
    select_parts = [
        "user_id",
        "date",
        "calories_in" if "calories_in" in cols_old else "NULL AS calories_in",
        "rest_calories" if "rest_calories" in cols_old else "NULL AS rest_calories",
        "workout_calories" if "workout_calories" in cols_old else "NULL AS workout_calories",
        "calories_out" if "calories_out" in cols_old else "NULL AS calories_out",
    ]
    if "net_calories" in cols_old:
        select_parts.append("net_calories")
    elif has_net:
        select_parts.append("net AS net_calories")
    else:
        select_parts.append("NULL AS net_calories")

    select_sql = "SELECT " + ", ".join(select_parts) + " FROM daily_summaries"

    # Copia dati
    conn.execute(f"""
    INSERT OR REPLACE INTO daily_summaries_new
      (user_id, date, calories_in, rest_calories, workout_calories, calories_out, net_calories)
    {select_sql}
    """)

    # Rimpiazzo tabella
    conn.execute("DROP TABLE daily_summaries")
    conn.execute("ALTER TABLE daily_summaries_new RENAME TO daily_summaries")

    conn.commit()


def init_db():
    _create_tables()
    _migrate_daily_summaries_if_needed()


init_db()