from datetime import date
from database import conn

def get_day_log(user_id: int, d: date):
    ds = str(d)
    return conn.execute(
        "SELECT morning_weight, is_closed FROM day_logs WHERE user_id=? AND date=?",
        (user_id, ds)
    ).fetchone()

def upsert_day_log(user_id: int, d: date, morning_weight=None, is_closed=None):
    ds = str(d)
    row = get_day_log(user_id, d)

    if row:
        mw = morning_weight if morning_weight is not None else row["morning_weight"]
        ic = int(is_closed) if is_closed is not None else row["is_closed"]
        conn.execute(
            "UPDATE day_logs SET morning_weight=?, is_closed=? WHERE user_id=? AND date=?",
            (mw, ic, user_id, ds)
        )
    else:
        conn.execute(
            "INSERT INTO day_logs (user_id, date, morning_weight, is_closed) VALUES (?,?,?,?)",
            (user_id, ds, morning_weight, int(is_closed or 0))
        )
    conn.commit()
