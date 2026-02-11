import pandas as pd
from database import conn

def safe_read_sql(query: str, params=()):
    try:
        return pd.read_sql(query, conn, params=params)
    except Exception:
        return pd.DataFrame()
