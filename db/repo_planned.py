from datetime import date
from database import conn
from db.common import safe_read_sql

def list_planned(user_id: int, ds: str):
    return safe_read_sql(
        """
        SELECT id, time, type, title, expected_calories, duration_min, status, notes
        FROM planned_events
        WHERE user_id=? AND date=?
        ORDER BY time
        """,
        (user_id, ds)
    )

def add_planned(
    user_id: int, ds: str, time_str: str, typ: str, title: str,
    expected_calories: float | None, duration_min: int | None, notes: str | None
):
    conn.execute(
        """
        INSERT INTO planned_events
          (user_id, date, time, type, title, expected_calories, duration_min, status, notes)
        VALUES (?,?,?,?,?,?,?,?,?)
        """,
        (user_id, ds, time_str, typ, title, expected_calories, duration_min, "planned", notes)
    )
    conn.commit()

def delete_planned(user_id: int, planned_id: int):
    conn.execute("DELETE FROM planned_events WHERE user_id=? AND id=?", (user_id, planned_id))
    conn.commit()

def mark_done(user_id: int, planned_id: int):
    conn.execute("UPDATE planned_events SET status='done' WHERE user_id=? AND id=?", (user_id, planned_id))
    conn.commit()
