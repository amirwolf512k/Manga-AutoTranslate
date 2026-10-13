# -*- coding: utf-8 -*-
"""تست v1.14.7 — اجرای موازی پچ‌های LaMa (فشار به CPU) + ادغام وابسته به صفحه"""
import io
import os
import sys
import time
from contextlib import redirect_stdout

import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manga  # noqa: E402

DYN = "/home/z/manga-work/lama-dyn/lama-manga-dyn.onnx"
ok = True


def check(name, cond, extra=""):
    global ok
    print(("  ✅ " if cond else "  ❌ ") + name + (f" — {extra}" if extra else ""))
    if not cond:
        ok = False


# ---------- ۱) ادغام وابسته به اندازهٔ صفحه ----------
print("[1] _group_nearby_patches — gap بزرگ‌تر = پچ کمتر")
# چهار حباب روی صفحهٔ بزرگ، هر جفت همسطر ~۳۰۰px فاصله
pending = [
    [100, 100, 500, 300, None, None, ""],
    [800, 120, 1200, 320, None, None, ""],
    [150, 600, 520, 820, None, None, ""],
    [760, 640, 1180, 860, None, None, ""],
]
g24 = manga.MangaTranslator._group_nearby_patches(pending, gap=24)
g92 = manga.MangaTranslator._group_nearby_patches(pending, gap=92)
check("gap=24 → ۴ پچ (بدون ادغام)", len(g24) == 4, f"{len(g24)} پچ")
# gap=92: فاصلهٔ افقی ۸۰۰-۵۰۰=۳۰۰ > ۱۹۲ → هنوز جدا؛ پس فقط عضوهای نزدیک ادغام می‌شوند
check("gap=92 → پچ ≤ ۴", len(g92) <= 4, f"{len(g92)} پچ")
# تست ادغام واقعی: دو خوشهٔ چسبیده
pending2 = [
    [100, 100, 500, 300, None, None, ""],
    [560, 120, 900, 320, None, None, ""],  # فاصلهٔ ۶۰px → با gap=92 ادغام
]
g2 = manga.MangaTranslator._group_nearby_patches(pending2, gap=92)
check("خوشهٔ ۶۰px نزدیک با gap=92 ادغام شد", len(g2) == 1, f"{len(g2)} پچ")

# ---------- ۲) موازی == ترتیبی (درستی + ایمنی نخ) ----------
print("[2] _lama_run_group — موازی باید با ترتیبی برابر باشد")
lama = manga.LamaMangaONNX(model_path=DYN, prefer_gpu=False, threads=2)
page = np.full((1200, 1600, 3), 246, np.uint8)
clusters = []
for (cx, cy) in ((300, 300), (1200, 280), (350, 900), (1250, 880)):
    cv2.ellipse(page, (cx, cy), (170, 110), 0, 0, 360, (250, 250, 250), -1)
    cv2.ellipse(page, (cx, cy), (170, 110), 0, 0, 360, (60, 60, 60), 2)
    for i in range(4):
        cv2.putText(page, "JAP", (cx - 120, cy - 45 + i * 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (40, 40, 40), 2)
    m = np.zeros((1200, 1600), np.uint8)
    cv2.rectangle(m, (cx - 150, cy - 90), (cx + 150, cy + 90), 255, -1)
    clusters.append([cx - 179, cy - 139, cx + 179, cy + 139,
                     m[cy - 139:cy + 139, cx - 179:cx + 179].copy(), None, ""])
kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))

# ترتیبی
seq_page = page.copy()
seq_cls = [list(c) for c in clusters]
t0 = time.time()
for c in seq_cls:
    manga.MangaTranslator._lama_run_group(
        manga.MangaTranslator, seq_page, [c], lama, kernel)
# 4 خوشهٔ جدا → ۴ گروه تک‌عضوی؛ مستقیم روی صفحه اعمال می‌کنیم
seq_out = seq_page.copy()
dt_seq = time.time() - t0

# موازی (دقیقاً مثل مسیر جدید clean_image)
par_page = page.copy()
par_cls = [list(c) for c in clusters]
from concurrent.futures import ThreadPoolExecutor
t0 = time.time()
with ThreadPoolExecutor(max_workers=2) as pex:
    futs = [pex.submit(manga.MangaTranslator._lama_run_group,
                       manga.MangaTranslator, par_page, [c], lama, kernel)
            for c in par_cls]
    for f in futs:
        f.result(timeout=600)
par_out = par_page.copy()
dt_par = time.time() - t0

diff = float(np.max(np.abs(seq_out.astype(np.int16) - par_out.astype(np.int16))))
check("خروجی موازی == ترتیبی", diff == 0, f"max diff={diff}")
check("موازی سریع‌تر یا برابر", dt_par <= dt_seq * 1.15,
      f"موازی {dt_par:.1f}s vs ترتیبی {dt_seq:.1f}s")
n_done = sum(1 for c in par_cls if c[6] == "LaMa")
check("همهٔ خوشه‌ها LaMa شدند", n_done == 4, f"{n_done}/4")

# ---------- ۳) clean_image پایان‌به‌پا با مسیر موازی ----------
print("[3] clean_image — فعال‌شدن مسیر موازی [🔥]")
os.environ["MANGA_LAMA_WORKERS"] = "2"  # شبیه گوشی کاربر (رم آزاد ~۱.۳GB → ۲ جریان)
FONT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts", "Vazirmatn-Regular.ttf")
if not os.path.isfile(FONT):
    FONT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts", "Lalezar-Regular.ttf")
mt = manga.MangaTranslator(api_key="TEST", provider="gemini", ocr_langs=["ja"], font_path=FONT)
mt.use_lama = True
mt.use_gpu = False
mt._lama = lama
mt._inpainter_name = "LaMa-Manga"
regions = []
rid = 0
for (cx, cy) in ((300, 300), (1200, 280), (350, 900), (1250, 880)):
    regions.append(manga.TextRegion(
        id=rid, boxes=[np.array([[cx - 150, cy - 90], [cx + 150, cy - 90],
                                 [cx + 150, cy + 90], [cx - 150, cy + 90]])],
        source_text="t", rect=(cx - 150, cy - 90, cx + 150, cy + 90)))
    rid += 1
buf = io.StringIO()
t0 = time.time()
with redirect_stdout(buf):
    cleaned = mt.clean_image(page.copy(), regions)
dt = time.time() - t0
log = buf.getvalue()
# 🩹 v1.14.15: حباب‌های یکنواختِ مصنوعی حالا با فلت‌فیلِ فوریِ K3 (خط/خوشه)
# حل می‌شوند — این خودش بردِ سرعت است و مسیر موازی فقط برای خوشه‌های
# LaMa-نیاز فعال می‌شود. درستیِ موازی بالا (بخش ۲) روی همان _lama_run_group
# اثبات شد؛ اینجا فقط پایان‌به‌پایی + حل‌شدن همهٔ خوشه‌ها چک می‌شود.
fast = ("instantly" in log) or ("[🔥]" in log) or ("[⚡]" in log) \
    or "'flat':" in log
check("پاکسازی پایان‌به‌پا تمام شد", cleaned.shape == page.shape, f"{dt:.1f}s")
check("مسیر سریع فعال (فلت‌فیل فوری یا موازی [🔥])", fast,
      [ln for ln in log.splitlines()
       if ("instantly" in ln or "[🔥]" in ln or "[⚡]" in ln
           or "Cleanup" in ln)][:2])
m = re.search(r"clusters → (\d+) patches", log) if (re := __import__("re")) else None
# 🩹 v1.14.15: اگر همهٔ خوشه‌ها فلت‌فیل شدند، هیچ پچ LaMa وجود ندارد — درست
check("تعداد پچ منطقی", (m is None and "'LaMa': 0" in log)
      or (m is not None and int(m.group(1)) <= 4),
      (m.group(1) + " پچ") if m else "بدون پچ LaMa (همه فلت)")

print()
print("نتیجه: " + ("همهٔ تست‌ها پاس ✅" if ok else "شکست ❌"))
sys.exit(0 if ok else 1)
