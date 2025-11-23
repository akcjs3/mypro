# db.py
import pymysql
from contextlib import contextmanager

DB_HOST = "127.0.0.1"
DB_PORT = 3306
DB_USER = "root"         
DB_PASSWORD = "1210"    
DB_NAME = "monitor_sketcher"

@contextmanager
def get_conn():
    conn = pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        db=DB_NAME,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False
    )
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def execute(query, params=None, fetchone=False, fetchall=False):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params or ())
            if fetchone:
                return cur.fetchone()
            if fetchall:
                return cur.fetchall()
