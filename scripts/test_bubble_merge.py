#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""تست ادغام حباب با داده‌های واقعی لاگ کاربر (صفحه sexyverse).

سناریوهای خراب قبل از فیکس:
  1) حباب «DON'T WORRY ... PARTY.» به دو تکه [23]/[24] شکسته می‌شد
     («HAVE OURSELVES» ↔ «A "HOUSE"» با vgap=5 و عرض نامساوی)
  2) کارت مشخصات (KAYLA SOMMERS / AGE: 37 / RACE: HUMAN) سه تکه می‌شد
  3) www.sexyversecomics.com (promo) به دیالوگ «نجات» داده می‌شد
"""
import sys

sys.path.insert(0, "/home/z/Manga-AutoTranslate")

try:
    import manga  # noqa
except Exception as e:
    print(f"[!] import manga failed: {e}")
    sys.exit(1)

from manga import MangaTranslator  # noqa

mt = MangaTranslator.__new__(MangaTranslator)
mt.debug = False


def det(text, x, y, w, h, kind="dialogue", conf=0.9):
    import numpy as np
    poly = np.array([[x, y], [x + w, y], [x + w, y + h], [x, y + h]], dtype=np.int32)
    return {"poly": poly, "text": text, "kind": kind, "conf": conf}


def kinds_of(regions):
    return [(r.kind, r.source_text) for r in regions]


fail = 0

# ---------- سناریو ۱: حباب ۹ خطی «DON'T WORRY ... PARTY.» ----------
bubble_lines = [
    det("DON'T WORRY",        500, 1500, 150, 20),
    det("SWEETIE.",           501, 1520, 140, 22),   # vgap=0 cx=3
    det("EVERYTHING WILL",    500, 1543, 160, 20),   # vgap=1
    det("BE FINE. NOW LET'S", 500, 1565, 165, 19),   # vgap=2
    det("GO INSIDE AND",      500, 1590, 155, 18),   # vgap=5
    det("HAVE OURSELVES",     500, 1613, 160, 17),   # vgap=5
    det('A "HOUSE"',          500, 1635, 95,  19),   # vgap=5 عرض کم!
    det("WARMING",            502, 1655, 100, 19),   # vgap=1
    det('PARTY."',            500, 1677, 90,  21),   # vgap=3
]
regions = mt.group_into_regions(bubble_lines)
dia = [r for r in regions if r.kind == "dialogue"]
merged_text = " ".join(r.source_text for r in dia)
ok1 = len(dia) == 1 and "PARTY" in dia[0].source_text and "DON'T WORRY" in dia[0].source_text
print(f"[تست ۱] حباب ۹خطی → {len(dia)} ناحیه: «{merged_text[:70]}» → {'PASS' if ok1 else 'FAIL'}")
fail += 0 if ok1 else 1

# ---------- سناریو ۲: کارت مشخصات ----------
card = [
    det("KAYLA SOMMERS", 100, 1030, 150, 15, conf=0.8),
    det("AGE: 37",       100, 1050, 60,  16, conf=0.8),
    det("RACE: HUMAN",   100, 1071, 105, 16, conf=0.8),
]
regions2 = mt.group_into_regions(card)
dia2 = [r for r in regions2 if r.kind == "dialogue"]
ok2 = len(dia2) == 1 and "KAYLA" in dia2[0].source_text and "RACE" in dia2[0].source_text
print(f"[تست ۲] کارت مشخصات → {len(dia2)} ناحیه: «{dia2[0].source_text if dia2 else ''}» → {'PASS' if ok2 else 'FAIL'}")
fail += 0 if ok2 else 1

# ---------- سناریو ۳: تبلیغ کنار حباب نباید دیالوگ شود ----------
ad_near = [
    det("www.sexyversecomics.com", 700, 300, 350, 22, kind="promo"),
    det("ASIDE FROM THE AGE GAP WE'RE JUST A NORMAL COUPLE.", 900, 330, 130, 90),
]
regions3 = mt.group_into_regions(ad_near)
kinds3 = kinds_of(regions3)
has_promo = any(k == "promo" for k, _ in kinds3)
n_dia = sum(1 for k, _ in kinds3 if k == "dialogue")
ok3 = has_promo and n_dia == 1
print(f"[تست ۳] URL کنار حباب → {[(k, t[:25]) for k, t in kinds3]} → {'PASS' if ok3 else 'FAIL'}")
fail += 0 if ok3 else 1

# ---------- سناریو ۴: دو حباب جدا با فاصلهٔ زیاد نباید ادغام شوند ----------
sep = [
    det("FIRST BUBBLE TEXT HERE",  500, 100, 150, 20),
    det("SECOND BUBBLE FAR BELOW", 500, 400, 150, 20),
]
regions4 = mt.group_into_regions(sep)
ok4 = len(regions4) == 2
print(f"[تست ۴] دو حباب جدا (گپ بزرگ) → {len(regions4)} ناحیه → {'PASS' if ok4 else 'FAIL'}")
fail += 0 if ok4 else 1

# ---------- سناریو ۵: گپ ۲۲px بدون خط واسط باید جدا بماند ----------
sep2 = [
    det("SHORT LINE ONE", 500, 100, 80, 18),
    det("DIFFERENT BUBBLE TEXT COMPLETELY", 500, 140, 220, 20),  # vgap=22
]
regions5 = mt.group_into_regions(sep2)
ok5 = len(regions5) == 2
print(f"[تست ۵] گپ ۲۲px بدون خط واسط → {len(regions5)} ناحیه → {'PASS' if ok5 else 'FAIL'}")
fail += 0 if ok5 else 1

print("=" * 40)
if fail == 0:
    print("ALL 5 TESTS PASSED")
    sys.exit(0)
else:
    print(f"{fail} TEST(S) FAILED")
    sys.exit(1)
