from database import conn
from db.common import safe_read_sql

def list_workouts(user_id: int, ds: str):
    return safe_read_sql(
        "SELECT id, time, description, duration_min, calories_burned, raw_json FROM workouts WHERE user_id=? AND date=? ORDER BY time",
        (user_id, ds)
    )

def insert_workout(user_id: int, ds: str, time_str: str, description: str, duration_min: int, calories_burned: float, raw_json: str | None):
    conn.execute(
        "INSERT INTO workouts (user_id, date, time, description, duration_min, calories_burned, raw_json) VALUES (?,?,?,?,?,?,?)",
        (user_id, ds, time_str, description, int(duration_min), float(calories_burned), raw_json),
    )
    conn.commit()

def delete_workout(user_id: int, workout_id: int):
    conn.execute("DELETE FROM workouts WHERE user_id=? AND id=?", (user_id, workout_id))
    conn.commit()
