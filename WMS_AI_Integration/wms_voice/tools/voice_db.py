"""
Umumiy savol-javob (QA) uchun haqiqiy bazadan grounding ma'lumoti.

MUHIM: bu modul deterministik PUTAWAY/PICK workflow'iga (mock_tasks.py)
DAXLDOR EMAS — faqat operator erkin savol berganda, javobni haqiqiy
ma'lumotga asoslash uchun ishlatiladi. Faqat SELECT, hech qanday yozuv yo'q.
"""
import os
from contextlib import contextmanager

import psycopg2
import psycopg2.extras
from psycopg2.pool import SimpleConnectionPool
from dotenv import load_dotenv

load_dotenv()


def _first_env(*names: str, default: str = "") -> str:
    for n in names:
        v = os.getenv(n)
        if v:
            return v
    return default


DB_HOST = _first_env("WMS_DB_HOST", "DB_HOST", default="192.168.1.7")
DB_PORT = _first_env("WMS_DB_PORT", "DB_PORT", default="5432")
DB_NAME = _first_env("WMS_DB_NAME", "DB_NAME", default="wmsdb")
DB_USER = _first_env("WMS_DB_USER", "DB_USER", default="read-user-wms")
DB_PASSWORD = _first_env(
    "WMS_DB_PASSWORD", "DB_PASSWORD",
    default="",  # MUHIM: parol FAQAT .env orqali beriladi
)

_pool: SimpleConnectionPool | None = None


def _get_pool() -> SimpleConnectionPool:
    global _pool
    if _pool is None:
        _pool = SimpleConnectionPool(
            minconn=1, maxconn=3,
            host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
            user=DB_USER, password=DB_PASSWORD,
        )
    return _pool


@contextmanager
def get_cursor():
    pool = _get_pool()
    conn = pool.getconn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


def get_task_status(task_id: int) -> dict | None:
    """warehouse_task jadvalidan bitta vazifaning to'liq holatini oladi."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT t.id, t.task_type, t.status, t.priority,
                   t.qty_target, t.qty_completed, t.block_reason,
                   t.from_bin, t.to_bin, t.notes,
                   p.name_uz AS product_name
            FROM public.warehouse_task t
            LEFT JOIN public.product p ON p.id = t.product_id
            WHERE t.id = %s AND t.is_delete = false;
            """,
            (task_id,),
        )
        return cur.fetchone()


def find_product_stock(name_fragment: str) -> list[dict]:
    """Mahsulot nomi bo'yicha qidirib, hozirgi qoldig'ini (bin bo'yicha) qaytaradi."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT p.name_uz, b.bin_code, b.zone, sb.qty_on_hand, sb.lot_number
            FROM public.product p
            JOIN public.inv_stock_balance sb ON sb.product_id = p.id
            LEFT JOIN public.inv_storage_bin b ON b.id = sb.storage_bin_id
            WHERE p.is_delete = false AND sb.is_delete = false
              AND sb.qty_on_hand > 0
              AND p.name_uz ILIKE %s
            ORDER BY sb.qty_on_hand DESC
            LIMIT 10;
            """,
            (f"%{name_fragment}%",),
        )
        return cur.fetchall()