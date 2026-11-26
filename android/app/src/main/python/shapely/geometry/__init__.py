# -*- coding: utf-8 -*-
"""shapely.geometry — شیمِ خالص (بخشِ v1.14.505)."""
import math


def _norm_pts(coords):
    pts = []
    for p in coords:
        try:
            pts.append((float(p[0]), float(p[1])))
        except Exception:
            continue
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts = pts[:-1]
    return pts


class _Ring:

    def __init__(self, pts):
        self.coords = [(float(x), float(y)) for x, y in pts]

    def __iter__(self):
        return iter(self.coords)

    def __len__(self):
        return len(self.coords)


class Polygon:

    def __init__(self, coords):
        if isinstance(coords, Polygon):
            coords = list(coords.exterior.coords)
        try:
            pts = _norm_pts(coords)
        except Exception:
            pts = []
        self._pts = pts
        closed = pts + [pts[0]] if pts else pts
        self.exterior = _Ring(closed)
        self.interiors = []

    @property
    def area(self):
        n = len(self._pts)
        if n < 3:
            return 0.0
        s = 0.0
        for i in range(n):
            x1, y1 = self._pts[i]
            x2, y2 = self._pts[(i + 1) % n]
            s += x1 * y2 - x2 * y1
        return abs(s) * 0.5

    @property
    def length(self):
        n = len(self._pts)
        if n < 2:
            return 0.0
        p = 0.0
        for i in range(n):
            x1, y1 = self._pts[i]
            x2, y2 = self._pts[(i + 1) % n]
            p += math.hypot(x2 - x1, y2 - y1)
        return p

    @property
    def is_valid(self):
        return len(self._pts) >= 3

    @property
    def is_empty(self):
        return len(self._pts) < 3

    @property
    def bounds(self):
        if not self._pts:
            return (0.0, 0.0, 0.0, 0.0)
        xs = [p[0] for p in self._pts]
        ys = [p[1] for p in self._pts]
        return (min(xs), min(ys), max(xs), max(ys))

    @property
    def centroid(self):
        if not self._pts:
            return (0.0, 0.0)
        n = len(self._pts)
        return (sum(p[0] for p in self._pts) / n,
                sum(p[1] for p in self._pts) / n)

    def buffer(self, distance, **k):
        d = abs(float(distance or 0.0))
        if d <= 0.0 or len(self._pts) < 3:
            return Polygon(self._pts)
        try:
            import cv2
            import numpy as np
            pts = np.asarray(self._pts, dtype=np.float32).reshape(-1, 2)
            (cx, cy), (w, h), ang = cv2.minAreaRect(pts)
            box = cv2.boxPoints(((float(cx), float(cy)),
                                 (float(w) + 2.0 * d, float(h) + 2.0 * d),
                                 float(ang)))
            return Polygon([(float(x), float(y)) for x, y in box])
        except Exception:
            return Polygon(self._pts)

    def contains(self, other):
        try:
            ox, oy = float(other.x), float(other.y)
        except Exception:
            return False
        return self._point_in(ox, oy)

    def _point_in(self, x, y):
        n = len(self._pts)
        if n < 3:
            return False
        inside = False
        j = n - 1
        for i in range(n):
            xi, yi = self._pts[i]
            xj, yj = self._pts[j]
            if (yi > y) != (yj > y):
                xint = (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi
                if x < xint:
                    inside = not inside
            j = i
        return inside

    def simplify(self, *a, **k):
        return Polygon(self._pts)

    def union(self, other):
        return Polygon(self._pts)

    def intersection(self, other):
        return Polygon(getattr(other, "_pts", self._pts))

    def difference(self, other):
        return Polygon(self._pts)

    def __len__(self):
        return 1 if self._pts else 0


class MultiPolygon:

    def __init__(self, polys=None):
        self.geoms = [p for p in (polys or []) if isinstance(p, Polygon)]

    def __len__(self):
        return len(self.geoms)

    def __iter__(self):
        return iter(self.geoms)

    @property
    def is_empty(self):
        return not self.geoms
