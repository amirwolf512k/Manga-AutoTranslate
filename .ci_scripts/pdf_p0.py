#!/usr/bin/env python3
"""v1.14.80 — صفحهٔ اولِ PDFِ خروجیِ امولاتور را JPG می‌کند (مقایسهٔ سریع با PC).

Usage: pdf_p0.py <key>          # key = u2/u3/u4/u5/u6/u7
Input : /tmp/emulout6/<key>.pdf
Output: /tmp/emulout6/<key>_p0.jpg
"""
import sys

import fitz

key = sys.argv[1]
doc = fitz.open(f"/tmp/emulout6/{key}.pdf")
pix = doc[0].get_pixmap(dpi=110)
pix.save(f"/tmp/emulout6/{key}_p0.jpg")
print(f"[✓] {key} pdf page0 rendered: {pix.width}x{pix.height}")
