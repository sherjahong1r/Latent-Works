# """
# test_promt.py — PROMPT'ni tez sinash uchun (bitta tayyor rasm bilan,
# 30 soniyalik siklsiz).

# Ishlatish: py test_promt.py rasm_nomi.png
# (fayl nomida probel bo'lsa, qo'shtirnoq ichiga oling: "rasm nomi.png")
# """

# import sys
# import json

# from vision_toolkit import read_dashboard_with_ai

# image_path = sys.argv[1] if len(sys.argv) > 1 else "test_promt.png"

# print(f"Rasm o'qilmoqda: {image_path}")
# print("AI'ga yuborilmoqda, biroz kuting...\n")

# result = read_dashboard_with_ai(image_path)

# print("=" * 60)
# print(json.dumps(result, ensure_ascii=False, indent=2))
# print("=" * 60)
