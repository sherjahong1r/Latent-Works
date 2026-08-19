"""
Umumiy WMS savol-javob mexanizmi — istalgan savolga (bitta yoki bir nechta
jadvaldan) javob beradi. Aloqasiz savolga aniq rad javobi qaytaradi.
"""
import re
import json
from contextlib import contextmanager

import psycopg2
import psycopg2.extras
from psycopg2.pool import SimpleConnectionPool

from shared.llm_client import ask_llm
from shared.config import SQL_MODEL, LLM_FAST_MODEL

import os
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
DB_PASSWORD = _first_env("WMS_DB_PASSWORD", "DB_PASSWORD", default="")

_pool: SimpleConnectionPool | None = None


def _get_pool() -> SimpleConnectionPool:
    global _pool
    if _pool is None:
        _pool = SimpleConnectionPool(
            minconn=1, maxconn=5,
            host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
            user=DB_USER, password=DB_PASSWORD,
        )
    return _pool


@contextmanager
def get_cursor(dict_cursor: bool = True):
    pool = _get_pool()
    conn = pool.getconn()
    try:
        factory = psycopg2.extras.RealDictCursor if dict_cursor else None
        with conn.cursor(cursor_factory=factory) as cur:
            cur.execute("SET statement_timeout = 8000;")
            yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


ALLOWED_TABLES = [
    "warehouse", "warehouse_group", "warehouse_layout", "warehouse_layout_element",
    "warehouse_task",
    "inv_storage_bin", "inv_bin_product_config", "inv_stock_balance",
    "inv_stock_ledger", "inv_stock_adjustment", "inv_stock_adjustment_line",
    "inv_stock_transfer", "inv_stock_transfer_line", "inv_batch",
    "inv_pick_task", "inv_pick_wave", "inv_putaway_rule", "inv_allocation",
    "inv_reservation", "inv_reservation_line", "inv_count", "inv_count_line",
    "inv_quality_inspection", "inv_short_pick", "inv_warehouse_load",
    "inv_warehouse_order",
    "product", "product_category", "product_bom",
    "prc_purchase_order", "prc_purchase_order_line",
    "prc_goods_receipt", "prc_goods_receipt_line",
    "receipt_order", "receipt_order_items",
    "plan_slotting_recommendation", "plan_labor_standard",
    "mxik", "measurement_unit", "rack_template",
    "wcs_exception_queue",
    "sls_shipment", "sls_shipment_line", "sls_shipment_package",
]

_schema_cache: str | None = None


def get_schema_description() -> str:
    global _schema_cache
    if _schema_cache:
        return _schema_cache

    lines = []
    with get_cursor(dict_cursor=False) as cur:
        for table in ALLOWED_TABLES:
            cur.execute(
                """
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = %s AND table_schema = 'public'
                ORDER BY ordinal_position;
                """,
                (table,),
            )
            cols = cur.fetchall()
            if not cols:
                continue
            col_str = ", ".join(f"{name}:{dtype}" for name, dtype in cols)
            lines.append(f"{table}({col_str})")

    _schema_cache = "\n".join(lines)
    return _schema_cache


_SQL_SYSTEM_PROMPT = """Sen WMS (ombor boshqaruv tizimi) uchun PostgreSQL SELECT so'rov generatoriisan.

QAT'IY QOIDALAR:
1. FAQAT bitta SELECT so'rov yoz. Hech qachon INSERT/UPDATE/DELETE/DROP/ALTER/TRUNCATE yozma.
2. FAQAT quyida berilgan jadval va ustunlardan foydalan. O'zingdan ustun yoki jadval nomini O'YLAB TOPMA.
3. SINONIMLAR VA MA'NONI TUSHUNISH: Foydalanuvchi so'zlarni har xil formatda so'rashi mumkin (masalan, "hudud", "joylashuv", "manzil" deganda `warehouse` jadvalidagi manzillar, nomlar yoki joylashuvga oid ustunlar nazarda tutiladi). Savol ombor/tovar/inventar/vazifaga tegishli bo'lsa, uni aloqasiz deb topma, balki mavjud ustunlar yordamida mantiqiy SELECT so'rovini tuz.
4. Uchta holatni farqla:
   a) Savol WMS mavzusiga umuman aloqasi yo'q — faqat bitta so'z qaytar: NOT_APPLICABLE
   b) Savol WMS mavzusiga oid, lekin berilgan jadval/ustunlar orasida buni topib bo'ladigan ma'lumot umuman yo'q — faqat bitta so'z qaytar: NO_DATA
   c) Aks holda — to'g'ri SQL SELECT so'rovini yoz.
5. Natijani har doim LIMIT 30 bilan cheklab qo'y.
6. Faqat SQL so'rovni (yoki NOT_APPLICABLE / NO_DATA so'zini) qaytar — boshqa matn yozma.

MAVJUD JADVALLAR VA USTUNLAR:
{schema}
"""


def _extract_sql(raw: str) -> str:
    cleaned = (raw or "").strip()
    if "```" in cleaned:
        parts = cleaned.split("```")
        cleaned = parts[1] if len(parts) > 1 else cleaned
        if cleaned.lower().startswith("sql"):
            cleaned = cleaned[3:]
    return cleaned.strip().rstrip(";").strip()


def _check_llm_error(raw: str):
    if raw and raw.strip().startswith("[LLM xatosi:"):
        raise RuntimeError(f"LLM ulanish xatosi: {raw}")
    if raw and raw.strip().startswith("[Vision xatosi:"):
        raise RuntimeError(f"Vision ulanish xatosi: {raw}")


def question_to_sql(question: str) -> str:
    schema = get_schema_description()
    prompt = _SQL_SYSTEM_PROMPT.format(schema=schema) + f'\n\nSAVOL: "{question}"\n\nJavob:'
    raw = ask_llm(prompt, model=SQL_MODEL)
    _check_llm_error(raw)
    return _extract_sql(raw)


_FORBIDDEN_KEYWORDS = [
    "insert", "update", "delete", "drop", "alter", "truncate",
    "grant", "revoke", "create", "--", "/*", ";",
]

def is_safe_select(sql: str) -> bool:
    s = sql.strip().lower()
    if not s or s in ("not_applicable", "no_data"):
        return False
    if not s.startswith("select"):
        return False
    if any(kw in s for kw in _FORBIDDEN_KEYWORDS):
        return False
    if not any(re.search(rf"\b{re.escape(t)}\b", s) for t in ALLOWED_TABLES):
        return False
    return True


def run_query(sql: str):
    with get_cursor(dict_cursor=True) as cur:
        cur.execute(sql)
        rows = cur.fetchall()
    return rows


def _summarize(question: str, rows: list) -> str:
    if not rows:
        return "Bazadan bu savolga mos ma'lumot topilmadi."

    preview = rows[:30]
    prompt = f"""Foydalanuvchi savoli: "{question}"

Baza so'rovi natijasi:
{json.dumps(preview, default=str, ensure_ascii=False)}

Shu ma'lumot asosida savolga O'ZBEK TILIDA, aniq va tushunarli javob yoz."""
    raw = ask_llm(prompt, model=LLM_FAST_MODEL)
    _check_llm_error(raw)
    return raw


def answer_question(text: str) -> dict:
    question = (text or "").strip()
    if not question:
        return {
            "on_topic": True,
            "answer": "Assalomu alaykum! Men WMS bo'yicha yordamchiman.",
            "sql": None,
        }

    try:
        sql = question_to_sql(question)
    except Exception as e:
        return {
            "on_topic": False,
            "answer": f"Kechirasiz, xato: {e}",
            "sql": None,
        }

    sql_lower = sql.strip().lower()

    if sql_lower == "not_applicable":
        return {
            "on_topic": False,
            "answer": "Kechirasiz, men faqat ombor/WMS tizimi haqidagi savollarga javob bera olaman.",
            "sql": None,
        }

    if sql_lower == "no_data":
        return {
            "on_topic": True,
            "answer": "Hozircha bu haqida ma'lumotimiz yo'q — SQL bazamizda topilmadi.",
            "sql": None,
        }

    if not is_safe_select(sql):
        return {
            "on_topic": True,
            "answer": "Hozircha bu haqida ma'lumotimiz yo'q — SQL bazamizda topilmadi.",
            "sql": sql,
        }

    try:
        rows = run_query(sql)
    except Exception as e:
        return {
            "on_topic": True,
            "answer": f"So'rovda xato: {e}",
            "sql": sql,
        }

    try:
        answer_text = _summarize(question, rows)
    except Exception as e:
        return {
            "on_topic": True,
            "answer": f"Javobni tuzishda xato: {e}",
            "sql": sql,
        }

    return {"on_topic": True, "answer": answer_text, "sql": sql, "row_count": len(rows)}