# -*- coding: utf-8 -*-
"""shapely — شیمِ خالصِ پایتن برای اندروید (v1.14.505).

shapely واقعی افزونهٔ C (GEOS) است و چرخِ اندرویدیِ cp310 ندارد.
rapidocr فقط «Polygon(quads).area و .length» را در unclipِ DB میخواهد؛
این شیم همان دو مقدار را با کفِ ریاضی (شوی‌لیس/محیط) دقیق میدهد و
چند متدِ رایجِ دیگر را هم به‌صورتِ معادل پیاده میکند.
رویِ PC هرگز نصب نمیشود (پکیجِ واقعی اولویت دارد).
"""
__version__ = "2.0.manga-shim"

from .geometry import MultiPolygon, Polygon  # noqa: F401
