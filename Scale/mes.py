"""
mes.py — Manufacturing Execution System (soddalashtirilgan).
PLC/SCADA'dan kelgan holatga qarab ishlab chiqarish partiyasini kuzatadi:
qachon boshlangan, nechta "yaxshi" birlik chiqarilgan, qancha to'xtash (downtime) bo'lgan.
"""

import datetime


class MESTracker:
    def __init__(self, conn):
        self.conn = conn
        self.current_batch = None
        self.downtime_sec = 0

    def start_batch(self, batch_no: str):
        with self.conn.cursor() as cur:
            cur.execute(
                """INSERT INTO mes_batches (batch_no, started_at, status)
                   VALUES (%s, %s, 'RUNNING') RETURNING id""",
                (batch_no, datetime.datetime.now()),
            )
            self.current_batch = cur.fetchone()[0]
        self.conn.commit()

    def update(self, trip_emergency: bool, cycle_seconds: int, good_unit_produced: bool):
        """Har PLC siklidan keyin chaqiriladi."""
        if self.current_batch is None:
            return

        if trip_emergency:
            self.downtime_sec += cycle_seconds
            with self.conn.cursor() as cur:
                cur.execute(
                    "UPDATE mes_batches SET downtime_sec = downtime_sec + %s WHERE id = %s",
                    (cycle_seconds, self.current_batch),
                )
            self.conn.commit()
        elif good_unit_produced:
            with self.conn.cursor() as cur:
                cur.execute(
                    "UPDATE mes_batches SET good_units = good_units + 1 WHERE id = %s",
                    (self.current_batch,),
                )
            self.conn.commit()

    def close_batch(self):
        if self.current_batch is None:
            return
        with self.conn.cursor() as cur:
            cur.execute(
                """UPDATE mes_batches SET status = 'COMPLETED', ended_at = %s
                   WHERE id = %s""",
                (datetime.datetime.now(), self.current_batch),
            )
        self.conn.commit()
        self.current_batch = None
