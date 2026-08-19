"""
Kompaniya/MVP haqidagi qisqartirilgan "bilim bazasi" — umumiy savol-javob
(QA) mexanizmi uchun statik kontekst. Manba: MES_WMS_AI_Integratsiyasi
hujjati (rahbariyat tomonidan tasdiqlangan MVP reja).

Bu — to'liq hujjat emas, faqat LLM'ga har safar berish uchun qisqa,
muhim qismlar. Operator "bu tizim nima qiladi", "qaysi funksiyalar bor"
kabi umumiy savol bersa, shu kontekst asosida javob beriladi.
"""

COMPANY_CONTEXT = """
KORXONA VA TIZIM HAQIDA UMUMIY MA'LUMOT:

Bu — MES (ishlab chiqarish) va WMS (ombor boshqaruvi) tizimlariga AI
yordamchilarni qo'shish loyihasi. Ikki mustaqil AI agent bor: MES Agent
va WMS Agent — ular bir-birining vazifalariga aralashmaydi, faqat o'z
sohasidagi ma'lumot bilan ishlaydi.

ASOSIY TAMOYIL: AI hech qachon o'z-o'zidan yozuv/o'zgartirish qilmaydi —
har doim odam (operator/menejer) tasdig'i kerak bo'ladi. Har bir javobda
ma'lumot manbasi va vaqti ko'rsatiladi.

WMS UCHUN TANLANGAN 4 TA AI FUNKSIYA (joriy loyihada amalga oshirilmoqda):

1. QABUL HUJJATI YORDAMCHISI — supplier hujjatini (ASN/packing-list)
   o'qib, PO bilan solishtiradi, tafovutlarni ko'rsatadi, receipt
   drafti tayyorlaydi. Yakuniy tasdiq operator tomonidan bo'ladi.

2. DINAMIK SLOTTING — kelayotgan tovar uchun aylanish tezligi, o'lcham,
   vazn, moslik, yaroqlilik muddati, masofa va sig'imga qarab eng mos
   ombor yacheykasini (bin) tavsiya qiladi.

3. OVOZ/SKANER VAZIFA YORDAMCHISI — operatorga joriy vazifani ovozda
   aytadi, ovozli javobini tinglaydi, lekin haqiqiy tasdiq faqat
   BARKOD SKANERI orqali bo'ladi — ovoz orqali hech narsa yozilmaydi.

4. CYCLE-COUNT USTUVORLIGI — harakat tarixi, tuzatishlar, qiymat va
   tekshiruv muddatiga asoslanib, qaysi ombor yacheykalarini birinchi
   navbatda jismoniy tekshirish (inventarizatsiya) kerakligini tavsiya
   qiladi.

QOLGAN (HOZIRCHA TANLANMAGAN, LEKIN HUJJATDA MAVJUD) FUNKSIYALAR:
- Ombor istisnolari copiloti — bloklangan vazifalar sababini tushuntiradi
- Picking route va wave optimallashtirish
- Ish yuklamasi prognozi
- Shikastlanish/pallet vision tekshiruvi
- Zaxirani tabiiy tilda tahlil qilish

XAVFSIZLIK QOIDALARI (barcha funksiyalar uchun umumiy):
- AI faqat TAVSIYA beradi, hech qachon o'zi WMS holatini o'zgartirmaydi
- Kritik amaldan oldin doimo odam tasdig'i talab qilinadi
- Ovoz orqali hech qanday tranzaksiya yozilmaydi — faqat skaner orqali
""".strip()
