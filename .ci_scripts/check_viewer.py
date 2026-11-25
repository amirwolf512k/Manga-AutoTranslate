# v1.14.504 — بررسیِ اسکرین‌شاتِ نمایشگر: باید محتوای واقعی رندر شده
# باشد — نه صفحهٔ سیاهِ خالی. معیار: نسبتِ پیکسلهای روشن (صفحهٔ
# مانگا زمینهٔ روشن دارد) و شلوغیِ لبه (متن/خطوط حباب).
import sys

import cv2
import numpy as np


def main(path):
    img = cv2.imread(path, cv2.IMREAD_COLOR)
    if img is None:
        print(f"[check-viewer] خواندن {path} ناموفق ✘")
        return 1
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = g.shape
    light = float((g > 150).mean())
    edges = cv2.Canny(cv2.resize(g, (w // 2, h // 2)), 60, 160)
    edge_pct = float((edges > 0).mean())
    mean_v = float(g.mean())
    print(f"[check-viewer] {w}x{h} | mean={mean_v:.1f} | "
          f"light={light * 100:.1f}% | edges={edge_pct * 100:.2f}%")
    ok = (light > 0.08) and (edge_pct > 0.004) and (mean_v > 14.0)
    if ok:
        print("[check-viewer] نمایشگر محتوا را نشان میدهد ✔")
        return 0
    print("[check-viewer] نمایشگر سیاه/خالی است ✘ "
          "(light>8% و edges>0.4% و mean>14 لازم است)")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else
                  "/tmp/emulout/viewer.png"))
