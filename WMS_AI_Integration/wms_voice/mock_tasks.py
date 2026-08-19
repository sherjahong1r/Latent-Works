"""
Ovoz yordamchisi uchun sinov vazifalari.

Keyinchalik real warehouse_task jadvaliga ulanadi (2-topshiriqdagi
slotting_db.py uslubida, faqat SELECT) — hozircha mock bilan mexanizmni
sinaymiz, xuddi 1- va 2-topshiriq boshida qilinganidek.
"""

_MOCK_TASKS = {
    "TASK-V001": {
        "task_id": "TASK-V001",
        "task_type": "PUTAWAY",
        "product_name": "Аммоний фосфат (аммофос)",
        "bin_code": "A01-01-03",
        "qty": 100,
        "uom": "kg",
    },
    "TASK-V002": {
        "task_id": "TASK-V002",
        "task_type": "PICK",
        "product_name": "Мочевина (карбамид)",
        "bin_code": "A01-01-02",
        "qty": 50,
        "uom": "kg",
    },
}


def get_task(task_id: str = None) -> dict:
    if task_id and task_id in _MOCK_TASKS:
        return _MOCK_TASKS[task_id]
    return next(iter(_MOCK_TASKS.values()))


def list_tasks() -> list:
    return list(_MOCK_TASKS.values())
