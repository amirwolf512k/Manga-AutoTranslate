# -*- coding: utf-8 -*-
"""تست v1.14.6 — فیکس سرعت شیم ORT + فیکس حباب رنگی"""
import os, sys, time
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


# ---------- ۱) شیم: سینتکس + API ----------
print("[1] شیم ORT اندروید")
shim_src = open("android/app/src/main/python/onnxruntime/__init__.py").read()
for token in ["_build_java_session_options", "setIntraOpNumThreads",
              "_tensor_out_to_numpy", "getFloatBuffer", "createSession(str(path_or_bytes), jopt)"]:
    check(f"شیم دارای {token}", token in shim_src)

# ---------- ۲) مدل داینامیک + نخ‌ها ----------
print("[2] LamaMangaONNX — لود و سرعت (نخ=۲ مثل گوشی)")
lama = manga.LamaMangaONNX(model_path=DYN, prefer_gpu=False, threads=2)
rng = np.random.default_rng(7)
base = np.full((304, 408, 3), 235, np.uint8)
base[..., 0] = np.clip(225 + rng.normal(0, 6, (304, 408)), 0, 255).astype(np.uint8)
yy, xx = np.mgrid[0:304, 0:408]
base = (base.astype(np.float32) + 12 * np.sin(yy / 14.0)[..., None]).astype(np.uint8)
mask = np.zeros((304, 408), np.uint8)
for cy, cx in ((90, 120), (200, 260)):
    cv2.rectangle(mask, (cx - 60, cy - 14), (cx + 60, cy + 14), 255, -1)
img_in = base.copy()
img_in[mask > 0] = 0
t0 = time.time()
out = np.array(lama(img_in, mask))
dt = time.time() - t0
check("پچ ۳۰۴×۴۰۸ اجرا شد", out.shape == base.shape, f"{dt:.2f}s")
check("سرعت منطقی (<9s لوکال)", dt < 9.0, f"{dt:.2f}s")

# ---------- ۳) حباب زرد رنگی ----------
print("[3] _color_fill_cluster — حباب زرد")
crop = np.full((160, 220, 3), 255, np.uint8)          # کاغذ سفید
cv2.ellipse(crop, (110, 80), (100, 70), 0, 0, 360, (40, 200, 250), -1)  # زرد
cv2.putText(crop, "TEXT TEXT", (30, 90), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (20, 20, 20), 3)
cmask = np.zeros((160, 220), np.uint8)
cv2.rectangle(cmask, (28, 68), (185, 100), 255, -1)
res = manga.MangaTranslator._color_fill_cluster(crop, cmask)
check("مسیر رنگی فعال شد", res is not None)
if res is not None:
    dil, outc = res
    med = np.median(outc[dil > 0], axis=0)
    check("رنگ پرش زرد است (آبی‌کانال پایین)", med[0] < 140, f"BGR={med.round(0)}")

# حباب سفید نباید مسیر رنگی شود
crop2 = np.full((160, 220, 3), 245, np.uint8)
cv2.putText(crop2, "TEXT TEXT", (30, 90), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (20, 20, 20), 3)
check("پس‌زمینهٔ سفید → مسیر رنگی رد", manga.MangaTranslator._color_fill_cluster(crop2, cmask) is None)

# ---------- ۴) clean_image پایان‌به‌پا (با LaMa داینامیک) ----------
print("[4] clean_image — صفحهٔ مصنوعی با حباب زرد + متن")
page = np.full((640, 480, 3), 248, np.uint8)
cv2.ellipse(page, (140, 160), (120, 90), 0, 0, 360, (40, 200, 250), -1)   # زرد
cv2.ellipse(page, (360, 420), (100, 70), 0, 0, 360, (250, 250, 250), 2)   # سفید
for i, tx in enumerate(range(60, 230, 40)):
    cv2.putText(page, "JPN", (tx, 140 + (i % 2) * 34), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (30, 30, 30), 2)
    cv2.putText(page, "JPN", (300 + (i % 2) * 20, 400 + (i % 3) * 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (30, 30, 30), 2)
tr = manga.TextRegion(
    id=0, boxes=[np.array([[50, 110], [240, 110], [240, 210], [50, 210]])],
    source_text="t", rect=(50, 110, 240, 210))
tr2 = manga.TextRegion(id=1, boxes=[np.array([[290, 370], [440, 370], [440, 470], [290, 470]])],
                       source_text="t", rect=(290, 370, 440, 470))

FONT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts", "Vazirmatn-Regular.ttf")
if not os.path.isfile(FONT):
    FONT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts", "Lalezar-Regular.ttf")
mt = manga.MangaTranslator(api_key="TEST", provider="gemini", ocr_langs=["ja"], font_path=FONT)
mt.use_lama = True
mt.use_gpu = False
mt._lama = manga.LamaMangaONNX(model_path=DYN, prefer_gpu=False, threads=2)
mt._inpainter_name = "LaMa-Manga"
t0 = time.time()
cleaned = mt.clean_image(page.copy(), [tr, tr2])
dt = time.time() - t0
diff = float(np.mean(np.abs(cleaned.astype(np.int16) - page.astype(np.int16))))
check("پاکسازی تمام شد", cleaned.shape == page.shape, f"{dt:.1f}s، تغیر میانگین={diff:.1f}")
check("زمان منطقی (<40s لوکال)", dt < 40.0, f"{dt:.1f}s")
cv2.imwrite("/tmp/test_v146_out.jpg", cleaned)

print()
print("نتیجه: " + ("همهٔ تست‌ها پاس ✅" if ok else "شکست ❌"))
sys.exit(0 if ok else 1)
