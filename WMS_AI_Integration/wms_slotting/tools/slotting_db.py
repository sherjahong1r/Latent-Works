"""
Dinamik slotting uchun DB o'qish qatlami.

MUHIM: Bu modul faqat O'QIYDI (SELECT). Hech qanday INSERT/UPDATE/DELETE
qilmaydi — chunki AI faqat tavsiya beradi, WMS holatini o'zi o'zgartirmaydi
(hujjatdagi talab shu). Haqiqiy joylashtirish operator/WMS tomonidan
amalga oshiriladi.

.env faylida quyidagilar bo'lishi kerak (agar hali yo'q bo'lsa qo'shing):
    WMS_DB_HOST=192.168.1.7
    WMS_DB_PORT=5432
    WMS_DB_NAME=wmsdb
    WMS_DB_USER=read-user-wms
    WMS_DB_PASSWORD=...

Eslatma: hozircha to'g'ridan-to'g'ri Postgres'ga ulanadi (chunki hali
real WMS REST API orqali bin/stock ma'lumotlarini olish imkoniyati yo'q,
faqat DB read-user berilgan). Kelajakda real API tayyor bo'lsa, shu
fayldagi funksiyalarni o'zgartirib, ichini httpx so'roviga almashtirish
kifoya — chaqiruvchi kod (slotting_engine.py) o'zgarmaydi.
"""
import os
from contextlib import contextmanager

import psycopg2
import psycopg2.extras
from psycopg2.pool import SimpleConnectionPool
from dotenv import load_dotenv

load_dotenv()

def _first_env(*names: str, default: str = "") -> str:
    """Bir nechta mumkin bo'lgan .env nomidan birinchisini topib qaytaradi."""
    for n in names:
        v = os.getenv(n)
        if v:
            return v
    return default


DB_HOST = _first_env("WMS_DB_HOST", "DB_HOST", default="192.168.1.7")
DB_PORT = _first_env("WMS_DB_PORT", "DB_PORT", default="5432")
DB_NAME = _first_env("WMS_DB_NAME", "DB_NAME", default="wmsdb")
DB_USER = _first_env("WMS_DB_USER", "DB_USER", default="read-user-wms")
DB_PASSWORD = _first_env("WMS_DB_PASSWORD", "DB_PASSWORD",
                          # MUHIM: parol FAQAT .env orqali beriladi,
                          # kodda hech qanday haqiqiy qiymat saqlanmaydi.
                          default="")

# Maxsus/tizim binlari — yangi tovar joylashtirish uchun TAVSIYA QILINMAYDI
# (skrap, qayta ishlash, jarayondagi ishlab chiqarish, standart-katalog binlari)
EXCLUDED_BIN_PATTERNS = ["DEF-%", "%SCRAP%", "%REWORK%", "%WIP%"]

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
def get_cursor():
    """Har bir so'rov uchun pool'dan connection oladi, oxirida qaytaradi."""
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


def _bin_exclusion_sql(alias: str = "b") -> str:
    conds = " AND ".join(f"{alias}.bin_code NOT ILIKE %s" for _ in EXCLUDED_BIN_PATTERNS)
    return conds


def get_product(product_id: int) -> dict | None:
    """product jadvalidan bitta mahsulotni to'liq qaytaradi."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT id, name_uz, sku, barcode, product_type, category_id,
                   unit_weight_kg, height_cm, length_cm, width_cm,
                   is_expiry_tracked, is_lot_tracked, is_serial_tracked,
                   qc_required, measure_code
            FROM public.product
            WHERE id = %s AND is_delete = false;
            """,
            (product_id,),
        )
        return cur.fetchone()


def resolve_putaway_zone(warehouse_id: int, product_id: int | None,
                          category_id: int | None) -> str | None:
    """
    inv_putaway_rule jadvalidan shu ombor uchun eng mos zonani topadi.
    Ustuvorlik: mahsulot-maxsus qoida > kategoriya-maxsus qoida >
    umumiy (default) qoida, har biri ichida priority DESC bo'yicha.
    """
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT zone, priority, product_id, category_id
            FROM public.inv_putaway_rule
            WHERE warehouse_id = %s AND is_active = true AND is_delete = false
            ORDER BY priority DESC;
            """,
            (warehouse_id,),
        )
        rules = cur.fetchall()

    if not rules:
        return None

    # 1) mahsulotga xos qoida
    for r in rules:
        if product_id is not None and r["product_id"] == product_id:
            return r["zone"]
    # 2) kategoriyaga xos qoida
    for r in rules:
        if category_id is not None and r["category_id"] == category_id:
            return r["zone"]
    # 3) umumiy qoida (product_id va category_id bo'sh), eng yuqori priority
    for r in rules:
        if r["product_id"] is None and r["category_id"] is None:
            return r["zone"]
    # 4) hech biri mos kelmasa — eng yuqori priority'dagi qoidaning zonasi
    return rules[0]["zone"]


def get_candidate_bins_with_utilization(warehouse_id: int, zone: str,
                                         product_id: int | None) -> list[dict]:
    """
    Berilgan ombor+zonadagi barcha nomzod binlarni, hozirgi og'irlik
    bo'yicha bandligi va shu mahsulot allaqachon shu binda bor-yo'qligi
    bilan birga qaytaradi. Maxsus (DEF-/SCRAP-/REWORK-/WIP-) binlar va
    bloklangan/muzlatilgan/nofaol binlar chiqarib tashlanadi.
    """
    exclusion_sql = _bin_exclusion_sql("b")
    query = f"""
        SELECT
            b.id AS bin_id,
            b.bin_code,
            b.zone,
            b.bin_type,
            b.aisle,
            b.rack,
            b.shelf_level,
            b.travel_sequence,
            b.max_weight_kg,
            b.max_volume_m3,
            COALESCE(SUM(sb.qty_on_hand * COALESCE(p.unit_weight_kg, 0)), 0) AS used_weight_kg,
            COUNT(DISTINCT sb.product_id) FILTER (WHERE sb.qty_on_hand > 0) AS distinct_products,
            BOOL_OR(sb.product_id = %s AND sb.qty_on_hand > 0) AS has_same_product
        FROM public.inv_storage_bin b
        LEFT JOIN public.inv_stock_balance sb
            ON sb.storage_bin_id = b.id AND sb.is_delete = false
        LEFT JOIN public.product p ON p.id = sb.product_id
        WHERE b.warehouse_id = %s
          AND b.zone = %s
          AND b.is_active = true
          AND b.is_blocked = false
          AND b.is_frozen = false
          AND {exclusion_sql}
        GROUP BY b.id, b.bin_code, b.zone, b.bin_type, b.aisle, b.rack,
                 b.shelf_level, b.travel_sequence, b.max_weight_kg, b.max_volume_m3
        ORDER BY b.travel_sequence NULLS LAST;
    """
    params = [product_id, warehouse_id, zone] + EXCLUDED_BIN_PATTERNS
    with get_cursor() as cur:
        cur.execute(query, params)
        return cur.fetchall()


def find_product_by_name(material_name: str) -> dict | None:
    """
    OCR'dan kelgan tovar nomi (material_name) bo'yicha product jadvalidan
    eng yaqin mosni qidiradi. Aniq mos kelmasa None qaytaradi — bu holda
    slotting hali ham davom etadi (og'irlik/kategoriya operator/standart
    qiymatlar bilan to'ldiriladi).
    """
    name = (material_name or "").strip()
    if not name:
        return None

    with get_cursor() as cur:
        # 1) to'liq moslik (katta-kichik harfga sezgir emas)
        cur.execute(
            """
            SELECT id, name_uz, sku, category_id, unit_weight_kg, qc_required
            FROM public.product
            WHERE is_delete = false AND lower(name_uz) = lower(%s)
            LIMIT 1;
            """,
            (name,),
        )
        row = cur.fetchone()
        if row:
            return row

        # 2) qisman moslik — nom ichida uchraydimi
        cur.execute(
            """
            SELECT id, name_uz, sku, category_id, unit_weight_kg, qc_required
            FROM public.product
            WHERE is_delete = false AND name_uz ILIKE %s
            ORDER BY length(name_uz) ASC
            LIMIT 1;
            """,
            (f"%{name}%",),
        )
        return cur.fetchone()


def list_warehouses() -> list[dict]:
    """warehouse jadvalidan barcha faol omborlarni qaytaradi."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT id, name, address, code
            FROM public.warehouse
            WHERE is_delete = false AND is_active = true
            ORDER BY id;
            """
        )
        return cur.fetchall()


def _normalize(text: str) -> str:
    return (text or "").lower().replace("'", "").replace("’", "").strip()


# Manzillarda uchraydigan, joy nomini bildirmaydigan "shovqin" so'zlar —
# moslashtirishda hisobga olinmaydi.
_ADDRESS_STOPWORDS = {
    "sh.", "shahar", "shahri", "tuman", "tumani", "vil.", "viloyati",
    "ko'ch.", "kocha", "kochasi", "uy", "hududi", "yo'li", "km", "baza",
}


def _warehouse_ids_with_bins() -> set[int]:
    """Hozircha faqat qaysi omborlarda haqiqiy inv_storage_bin yozuvi
    borligini qaytaradi (masalan 7-16 omborlarda hali bin yo'qligi
    tasdiqlangan edi)."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT warehouse_id FROM public.inv_storage_bin
            WHERE is_active = true;
            """
        )
        return {row["warehouse_id"] for row in cur.fetchall()}


def match_warehouses_by_text(text: str) -> list[dict]:
    """
    Hujjatdan o'qilgan manzil matnini `warehouse.address`/`warehouse.name`
    bilan solishtirib, mos kelgan omborlar ro'yxatini qaytaradi (0, 1 yoki
    bir nechta bo'lishi mumkin — bir nechta bo'lsa, chaqiruvchi kod
    operatordan aniqlashtirish so'rashi kerak, TAXMIN QILMASLIK kerak).
    """
    text_norm = _normalize(text)
    if not text_norm:
        return []

    warehouses = list_warehouses()
    scored = []
    for w in warehouses:
        addr = w.get("address") or ""
        addr_norm = _normalize(addr)
        if not addr_norm:
            continue
        tokens = [t for t in addr_norm.replace(",", " ").split()
                  if t not in _ADDRESS_STOPWORDS and len(t) > 2]
        if not tokens:
            continue
        matched = sum(1 for t in tokens if t in text_norm)
        score = matched / len(tokens)
        if score >= 0.5:  # manzil so'zlarining kamida yarmi topilishi kerak
            scored.append((score, w))

    scored.sort(key=lambda x: -x[0])
    # Faqat eng yuqori ballga teng bo'lganlarni qaytaramiz (masalan bir xil
    # manzilli 2 ta ombor bo'lsa — ikkalasi ham "nomzod" bo'lib qoladi)
    if not scored:
        return []
    top_score = scored[0][0]
    candidates = [w for s, w in scored if s >= top_score - 1e-9]

    # MUHIM: agar bir nechta ombor bir xil manzilga ega bo'lsa (masalan
    # id=1 va id=7), ular orasidan FAQAT jismoniy bin (inv_storage_bin)
    # mavjud bo'lganlarini afzal ko'ramiz — chunki bin'i yo'q omborga
    # baribir hech qanday tavsiya bera olmaymiz. Agar bittasi qolsa,
    # noaniqlik o'zi hal bo'ladi.
    with_bins = _warehouse_ids_with_bins()
    filtered = [c for c in candidates if c["id"] in with_bins]
    if filtered:
        return filtered
    return candidates  # hech birida bin bo'lmasa, hammasini qaytaramiz


def get_open_putaway_tasks(warehouse_id: int, limit: int = 50) -> list[dict]:
    """
    warehouse_task jadvalidan hali bin tayinlanmagan (to_bin_id bo'sh)
    PUTAWAY vazifalarini qaytaradi — bular AI tavsiyasiga muhtoj bo'lgan
    haqiqiy vazifalar ro'yxati.
    """
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT id, product_id, warehouse_id, qty_target, qty_completed,
                   lot_number, serial_number, status, reference_type,
                   reference_doc_no, to_bin, to_bin_id, priority,
                   datetime_created
            FROM public.warehouse_task
            WHERE warehouse_id = %s
              AND task_type = 'PUTAWAY'
              AND status IN ('CREATED', 'IN_PROGRESS')
              AND to_bin_id IS NULL
              AND is_delete = false
            ORDER BY priority DESC, datetime_created ASC
            LIMIT %s;
            """,
            (warehouse_id, limit),
        )
        return cur.fetchall()