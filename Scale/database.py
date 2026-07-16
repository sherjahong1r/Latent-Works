"""
database.py — PostgreSQL bilan ishlash (Historian qatlami).
psycopg (3-versiya) kutubxonasidan foydalanadi — Python 3.13 uchun ham
tayyor (prebuilt) binary fayllarga ega, shuning uchun Windows'da qurish
(compile) muammosi bo'lmaydi.
"""

import psycopg
from psycopg.rows import dict_row
from config import DB_CONFIG


def get_connection():
    return psycopg.connect(**DB_CONFIG)


def init_db():
    """db/schema.sql faylini ishga tushirib jadvallarni yaratadi."""
    with open("db/schema.sql", "r") as f:
        sql = f.read()
    conn = get_connection()
    with conn, conn.cursor() as cur:
        cur.execute(sql)
    conn.close()


def insert_reading(conn, readings: dict):
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO sensor_readings
               (temperature, pressure, heat_output, speed, ph, flow_rate,
                level_pct, vibration, humidity, voltage, current_a)
               VALUES (%(temperature)s, %(pressure)s, %(heat_output)s, %(speed)s,
                       %(ph)s, %(flow_rate)s, %(level_pct)s, %(vibration)s,
                       %(humidity)s, %(voltage)s, %(current_a)s)""",
            readings,
        )
    conn.commit()


def insert_actuator_state(conn, state: dict):
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO actuator_states
               (fan_on, relief_valve_open, neutralizer_pump_on, agitator_on, trip_emergency)
               VALUES (%(fan_on)s, %(relief_valve_open)s, %(neutralizer_pump_on)s,
                       %(agitator_on)s, %(trip_emergency)s)""",
            state,
        )
    conn.commit()


def insert_alarm(conn, severity: str, message: str):
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO alarms (severity, message) VALUES (%s, %s)",
            (severity, message),
        )
    conn.commit()


def insert_ai_insight(conn, sensor_name: str, finding: str, z_score: float):
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO ai_insights (sensor_name, finding, z_score)
               VALUES (%s, %s, %s)""",
            (sensor_name, finding, z_score),
        )
    conn.commit()


def fetch_recent_readings(conn, limit: int = 50):
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT * FROM sensor_readings ORDER BY id DESC LIMIT %s", (limit,)
        )
        rows = cur.fetchall()
    return list(reversed(rows))


def fetch_recent_alarms(conn, limit: int = 20):
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT * FROM alarms ORDER BY id DESC LIMIT %s", (limit,)
        )
        return cur.fetchall()


def fetch_latest_actuator_state(conn):
    """Eng so'nggi aktuator holatini (fan, klapan va h.k.) qaytaradi."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT * FROM actuator_states ORDER BY id DESC LIMIT 1"
        )
        return cur.fetchone()


def fetch_history_for_sensor(conn, sensor_name: str, limit: int = 200):
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT {sensor_name} FROM sensor_readings ORDER BY id DESC LIMIT %s",
            (limit,),
        )
        rows = cur.fetchall()
    return [r[0] for r in rows if r[0] is not None]
