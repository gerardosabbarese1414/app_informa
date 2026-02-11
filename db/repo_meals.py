from database import conn
from db.common import safe_read_sql

def list_meals(user_id: int, ds: str):
    return safe_read_sql(
        "SELECT id, time, description, calories, raw_json FROM meals WHERE user_id=? AND date=? ORDER BY time",
        (user_id, ds)
    )

def insert_meal(user_id: int, ds: str, time_str: str, description: str, calories: float, raw_json: str | None):
    conn.execute(
        "INSERT INTO meals (user_id, date, time, description, calories, raw_json) VALUES (?,?,?,?,?,?)",
        (user_id, ds, time_str, description, float(calories), raw_json),
    )
    conn.commit()

def delete_meal(user_id: int, meal_id: int):
    conn.execute("DELETE FROM meals WHERE user_id=? AND id=?", (user_id, meal_id))
    conn.commit()
