# -*- coding: utf-8 -*-
"""pyclipper — شیمِ خالصِ پایتن برای اندروید (v1.14.505).

pyclipper واقعی افزونهٔ C است و چرخِ اندرویدیِ cp310 برایش وجود ندارد؛
rapidocr فقط از PyclipperOffset.Execute(delta) برای «unclip» جعبه‌های
متن استفاده میکند و ورودی‌اش همیشه کوادِ خروجیِ minAreaRect است که
بلافاصله بعدِ Expand دوباره minAreaRect میشود — پس گسترشِ مستطیلِ
minAreaRect به اندازهٔ delta در هر سمت، ریاضیاتاً معادلِ خروجیِ
PyclipperOffset (JT_ROUND) برای همین ورودیهاست (پدِ 2×delta در w/h).
این شیم رویِ PC هرگز نصب نمیشود (پکیجِ واقعی اولویت دارد).
"""
import cv2
import numpy as np

JT_ROUND = 2
JT_MITER = 1
JT_SQUARE = 0

ET_CLOSEDPOLYGON = 1
ET_OPENROUND = 2
ET_OPENSQUARE = 3
ET_OPENBUTT = 4

PT_SUBJECT = 0
PT_CLIP = 1

CT_INTERSECTION = 0
CT_UNION = 1
CT_DIFFERENCE = 2
CT_XOR = 3

PFT_EVENODD = 0
PFT_NONZERO = 1


def _as_pts(path):
    try:
        pts = np.asarray(path, dtype=np.float64).reshape(-1, 2)
        if pts.shape[0] < 1 or not np.isfinite(pts).all():
            return None
        return pts
    except Exception:
        return None


def _offset_path(pts, delta):
    """گسترشِ چندضلعی به بیرون با delta — معادلِ Execute(delta) پیکلیپر."""
    d = abs(float(delta))
    if pts.shape[0] < 3:
        return None
    try:
        (cx, cy), (w, h), ang = cv2.minAreaRect(pts.astype(np.float32))
    except Exception:
        return None
    w2 = float(w) + 2.0 * d
    h2 = float(h) + 2.0 * d
    if w2 <= 0.0 or h2 <= 0.0:
        return None
    box = cv2.boxPoints(((float(cx), float(cy)), (w2, h2), float(ang)))
    return [[int(round(float(x))), int(round(float(y)))] for x, y in box]


def _bbox_path(pts, delta):
    d = abs(float(delta))
    try:
        x0, y0 = float(np.min(pts[:, 0])), float(np.min(pts[:, 1]))
        x1, y1 = float(np.max(pts[:, 0])), float(np.max(pts[:, 1]))
    except Exception:
        return None
    return [[int(round(x0 - d)), int(round(y0 - d))],
            [int(round(x1 + d)), int(round(y0 - d))],
            [int(round(x1 + d)), int(round(y1 + d))],
            [int(round(x0 - d)), int(round(y1 + d))]]


class PyclipperOffset:

    def __init__(self, *a, **k):
        self._paths = []

    def AddPath(self, path, join_type=None, end_type=None):
        pts = _as_pts(path)
        if pts is None:
            return False
        self._paths.append(pts)
        return True

    def AddPaths(self, paths, join_type=None, end_type=None):
        ok = True
        for p in (paths or []):
            ok = self.AddPath(p, join_type, end_type) and ok
        return ok

    def Execute(self, delta):
        out = []
        for pts in self._paths:
            grown = _offset_path(pts, delta)
            if grown is None:
                grown = _bbox_path(pts, delta)
            if grown is not None and len(grown) >= 3:
                out.append(grown)
        return out

    def Clear(self):
        self._paths = []


class Pyclipper:

    def __init__(self, *a, **k):
        pass

    def AddPath(self, *a, **k):
        return True

    def AddPaths(self, *a, **k):
        return True

    def Execute(self, *a, **k):
        return []

    def Clear(self):
        pass


def SimplifyPath(path, fill_type=1):
    pts = _as_pts(path)
    if pts is None:
        return []
    return [[int(round(float(x))), int(round(float(y)))] for x, y in pts]


def ScaleUp(value, scale=1.0):
    return value


def ScaleDown(value, scale=1.0):
    return value


def Area(poly):
    pts = _as_pts(poly)
    if pts is None or pts.shape[0] < 3:
        return 0.0
    x = pts[:, 0]
    y = pts[:, 1]
    s = float(np.dot(x, np.roll(y, -1)) - np.dot(np.roll(x, -1), y))
    return abs(s) * 0.5


def Orientation(poly):
    pts = _as_pts(poly)
    if pts is None or pts.shape[0] < 3:
        return True
    x = pts[:, 0]
    y = pts[:, 1]
    s = float(np.dot(x, np.roll(y, -1)) - np.dot(np.roll(x, -1), y))
    return s >= 0.0


def ReversePath(path):
    pts = _as_pts(path)
    if pts is None:
        return []
    return [[float(p[0]), float(p[1])] for p in pts[::-1]]
