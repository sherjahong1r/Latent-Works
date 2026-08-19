"""WMS Agent uchun promptlar."""

SYSTEM_PROMPT = """Sen ombor qabul yordamchisisan.
Vazifang: tovar hujjatini PO bilan taqqoslab, 
qisqa va tushunarli hisobot berish.
O'zbek tilida yoz. Faqat tovar miqdorlariga e'tibor ber."""


def receipt_comparison_prompt(ocr_data: dict, po_data: dict, differences: dict) -> str:
    mos = differences.get("mos_tovarlar", [])
    farqlar = differences.get("farqlar", [])
    xulosa = differences.get("xulosa", "")

    return f"""
Quyidagi tovar qabul natijasini qisqa va tushunarli qilib yoz:

TO'LIQ KELGAN TOVARLAR ({len(mos)} ta):
{mos}

MUAMMOLI TOVARLAR ({len(farqlar)} ta):
{farqlar}

UMUMIY XULOSA: {xulosa}

Hisobotni quyidagi formatda yoz:

QABUL NATIJASI:
✅ To'liq kelgan: [tovarlar ro'yxati]
❌ Kamchilik: [tovar nomi — qancha kam]
⚠️ Ortiqcha: [tovar nomi — qancha ortiq]

XULOSA: [TO'LIQ yoki TO'LIQ EMAS]
[Agar to'liq emas bo'lsa — nima qilish kerak]

Operator tasdiqlashi kerakligini eslatib qo'y.
"""


def exception_explainer_prompt(task, bin_info, inventory) -> str:
    return f"""
Ombor istisnosi:
Vazifa: {task}
Bin: {bin_info}
Zaxira: {inventory}

Qisqa tushuntir: nima muammo, kim hal qiladi, keyingi qadam.
"""


def voice_task_prompt(question, inventory, tasks) -> str:
    return f"""
Operator savoli: {question}
Zaxira: {inventory}
Vazifalar: {tasks}

Qisqa va aniq javob ber (3-4 gap).
"""