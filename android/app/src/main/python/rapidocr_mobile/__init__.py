# -*- coding: utf-8 -*-
"""rapidocr_mobile — موتورِ PP-OCRv6 سبک برایِ اندروید (v1.14.123).

دیکدِ K3 v4.1.1 (درخواستِ کاربر: «K3 چطور سریع و کامل استخراج میزنه؟»)
نشان داد K3 رویِ گوشی همان پایپلاینِ ONNXِ پی‌سی را اجرا میکند:
  ComicDetectorService (باکسِ حباب) → RunRapidOcrPipelineOnCrop /
  RunPaddleOcrV5RecWithSession → _ppOcrDict (ppocrv6_dict.txt)
  → SlicerGroupNearbyBlocks / MergeOcrBlocks → LaMa (LinearLama).

این ماژول همان پایپلاینِ RapidOCRِ پکیجِ PC را «بدونِ وابستگیِ
extra» بازسازی میکند تا داخلِ APK (Chaquopy) اجرا شود:
  • det: PP-OCRv6_det_small.onnx (DBNet) — پارامترهایِ عینِ
    config.yamlِ rapidocr (limit=736/min، thresh=0.3، box_thresh=0.5،
    unclip=1.6، dilation=2×2، score_mode=fast)
  • rec: PP-OCRv6_rec_small.onnx (CTC) — 3×48×W، بچِ ۶، دیکشنریِ
    «داخلِ خودِ مدل» (ppocrv6_chars.txt = metadataِ `character`
    استخراجشده از فایلِ onnxِ همان مدل)
  • unclip بدونِ pyclipper/shapely (پدِ مستطیلِ minAreaRect —
    ریاضیاتاً معادلِ خروجیِ PyclipperOffset برایِ rect)
  • سشن = شیمِ onnxruntimeِ باندلشده (پلِ Java ORT-android)

خروجیِ `ocr()` همان قالبِ RapidOCRBackend است:
  [ [box(np.float32 4×2), (text, score)], ... ]
"""
import math
import os

import cv2
import numpy as np

import onnxruntime  # رویِ اندروید = شیمِ پلِ Java ORT؛ رویِ PC = پکیجِ واقعی

_HERE = os.path.dirname(os.path.abspath(__file__))
_CHARS_TXT = os.path.join(_HERE, "ppocrv6_chars.txt")


def _load_charset(path: str = _CHARS_TXT):
    """['blank'] + سطرهایِ dict + [' '] — دقیقاً قراردادِ PP-OCR CTC."""
    with open(path, "r", encoding="utf-8") as f:
        chars = [ln.rstrip("\n\r") for ln in f]
    chars = [c for c in chars if c != ""]
    return ["blank"] + chars + [" "]


class _Sess:
    def __init__(self, path: str, intra: int):
        so = onnxruntime.SessionOptions()
        so.intra_op_num_threads = max(1, int(intra))
        so.inter_op_num_threads = 1
        ep = str(os.environ.get("MANGA_MOBILE_OCR_EP", "") or "").strip()
        self.sess = onnxruntime.InferenceSession(
            path, sess_options=so, providers=None)
        self.in_name = self.sess.get_inputs()[0].name
        self.out_name = self.sess.get_outputs()[0].name

    def __call__(self, x: np.ndarray) -> np.ndarray:
        outs = self.sess.run(None, {self.in_name: x})
        return outs[0]


class RapidOcrMobile:
    """PP-OCRv6 det+rec — عینِ پیشفرضهایِ rapidocr config.yaml."""

    def __init__(self, det_path: str, rec_path: str,
                 charset_path: str = _CHARS_TXT, intra_threads: int = 4,
                 limit_side_len: int = 736, thresh: float = 0.3,
                 box_thresh: float = 0.5, unclip_ratio: float = 1.6,
                 max_candidates: int = 1000, text_score: float = 0.5,
                 rec_img_shape=(3, 48, 320), rec_batch_num: int = 6):
        self.det = _Sess(det_path, intra_threads)
        self.rec = _Sess(rec_path, intra_threads)
        self.character = _load_charset(charset_path)
        self.limit_side_len = int(limit_side_len)
        self.thresh = float(thresh)
        self.box_thresh = float(box_thresh)
        self.unclip_ratio = float(unclip_ratio)
        self.max_candidates = int(max_candidates)
        self.text_score = float(text_score)
        self.rec_img_shape = tuple(rec_img_shape)
        self.rec_batch_num = int(rec_batch_num)
        self.min_size = 3
        self.dilation_kernel = np.array([[1, 1], [1, 1]], dtype=np.uint8)

    # ─────────────────────────── det ───────────────────────────

    def _det_preprocess(self, img: np.ndarray):
        h, w = img.shape[:2]
        if min(h, w) < self.limit_side_len:
            ratio = (float(self.limit_side_len) / h) if h < w else \
                (float(self.limit_side_len) / w)
        else:
            ratio = 1.0
        resize_h = int(round((int(h * ratio)) / 32) * 32)
        resize_w = int(round((int(w * ratio)) / 32) * 32)
        if resize_w <= 0 or resize_h <= 0:
            return None
        if (resize_h, resize_w) != (h, w):
            img = cv2.resize(img, (resize_w, resize_h))
        out = (img.astype("float32") * (1.0 / 255.0) - 0.5) / 0.5
        out = out.transpose((2, 0, 1))
        return np.expand_dims(out, axis=0).astype(np.float32)

    def _get_mini_boxes(self, contour: np.ndarray):
        bounding_box = cv2.minAreaRect(contour)
        points = sorted(list(cv2.boxPoints(bounding_box)), key=lambda x: x[0])

        index_1, index_2, index_3, index_4 = 0, 1, 2, 3
        if points[1][1] > points[0][1]:
            index_1, index_4 = 0, 1
        else:
            index_1, index_4 = 1, 0
        if points[3][1] > points[2][1]:
            index_2, index_3 = 2, 3
        else:
            index_2, index_3 = 3, 2

        box = np.array([points[index_1], points[index_2],
                        points[index_3], points[index_4]])
        return box, min(bounding_box[1])

    @staticmethod
    def _box_score_fast(bitmap: np.ndarray, _box: np.ndarray) -> float:
        h, w = bitmap.shape[:2]
        box = _box.copy()
        xmin = int(np.clip(np.floor(box[:, 0].min()), 0, w - 1))
        xmax = int(np.clip(np.ceil(box[:, 0].max()), 0, w - 1))
        ymin = int(np.clip(np.floor(box[:, 1].min()), 0, h - 1))
        ymax = int(np.clip(np.ceil(box[:, 1].max()), 0, h - 1))
        mask = np.zeros((ymax - ymin + 1, xmax - xmin + 1), dtype=np.uint8)
        box[:, 0] = box[:, 0] - xmin
        box[:, 1] = box[:, 1] - ymin
        cv2.fillPoly(mask, box.reshape(1, -1, 2).astype(np.int32), 1)
        return float(cv2.mean(bitmap[ymin:ymax + 1, xmin:xmax + 1], mask)[0])

    def _unclip(self, box: np.ndarray) -> np.ndarray:
        """معادلِ PyclipperOffset(JT_ROUND, distance=area*ratio/length).

        ورودی: ۴ گوشهٔ rect (ترتیبِ حلقه: TL,TR,BR,BL — خروجیِ
        _get_mini_boxes). هر گوشه به اندازهٔ dist در جهتِ دو ضلعِ مجاور
        بیرون میرود — برایِ rect دقیقاً معادلِ offsetِ کلایپر است
        (گوشههایِ گردِ JT_ROUND بعداً minAreaRect میشوند = همان rect)."""
        pts = np.asarray(box, dtype=np.float32).reshape(-1, 2)
        # rect واقعی از طولِ ضلعها (حلقهٔ TL,TR,BR,BL)
        w1 = float(np.linalg.norm(pts[1] - pts[0]))
        h1 = float(np.linalg.norm(pts[3] - pts[0]))
        area = max(1.0, w1 * h1)
        perim = max(1.0, 2.0 * (w1 + h1))
        dist = area * self.unclip_ratio / perim
        out = np.empty_like(pts)
        n = len(pts)
        for i in range(n):
            prev = pts[(i - 1) % n]
            nxt = pts[(i + 1) % n]
            d1 = pts[i] - prev
            d2 = pts[i] - nxt
            n1 = np.linalg.norm(d1)
            n2 = np.linalg.norm(d2)
            if n1 < 1e-6 or n2 < 1e-6:
                out[i] = pts[i]
                continue
            out[i] = pts[i] + dist * (d1 / n1 + d2 / n2)
        return out.reshape((-1, 1, 2))

    def _order_points_clockwise(self, pts: np.ndarray) -> np.ndarray:
        """عینِ rapidocr: sort بر اساسِ x، سپسِ جفتِ بالا/پایین."""
        points = sorted(list(pts), key=lambda x: x[0])
        if points[1][1] > points[0][1]:
            p1, p4 = points[0], points[1]
        else:
            p1, p4 = points[1], points[0]
        if points[3][1] > points[2][1]:
            p2, p3 = points[2], points[3]
        else:
            p2, p3 = points[3], points[2]
        return np.array([p1, p2, p3, p4], dtype=np.float32)

    def _det_postprocess(self, pred: np.ndarray, src_h: int, src_w: int):
        pred = pred[:, 0, :, :]  # [1,H,W]
        mask = (pred[0] > self.thresh).astype(np.uint8)  # [H,W]
        mask = cv2.dilate(mask, self.dilation_kernel)
        bitmap = mask
        height, width = bitmap.shape

        outs = cv2.findContours(
            (bitmap * 255).astype(np.uint8),
            cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        contours = outs[1] if len(outs) == 3 else outs[0]

        num = min(len(contours), self.max_candidates)
        boxes, scores = [], []
        for idx in range(num):
            contour = contours[idx]
            points, sside = self._get_mini_boxes(contour)
            if sside < self.min_size:
                continue
            score = self._box_score_fast(pred[0], points.reshape(-1, 2))
            if self.box_thresh > score:
                continue
            box = self._unclip(points)
            box, sside = self._get_mini_boxes(box)
            if sside < self.min_size + 2:
                continue
            box[:, 0] = np.clip(np.round(box[:, 0] / width * src_w), 0, src_w)
            box[:, 1] = np.clip(np.round(box[:, 1] / height * src_h), 0, src_h)
            boxes.append(box.astype(np.float32))
            scores.append(float(score))
        return boxes, scores

    def _detect(self, img: np.ndarray):
        src_h, src_w = img.shape[:2]
        pre = self._det_preprocess(img)
        if pre is None:
            return []
        pred = self.det(pre)
        boxes, scores = self._det_postprocess(pred, src_h, src_w)

        # filter_det_res: مرتبسازیِ ساعتگرد + حذفِ ضلعِ ≤3
        final = []
        for box, score in zip(boxes, scores):
            box = self._order_points_clockwise(box)
            box[:, 0] = np.clip(box[:, 0], 0, src_w - 1)
            box[:, 1] = np.clip(box[:, 1], 0, src_h - 1)
            wdt = int(np.linalg.norm(box[0] - box[1]))
            hgt = int(np.linalg.norm(box[0] - box[3]))
            if wdt <= 3 or hgt <= 3:
                continue
            final.append((box, score))

        # sorted_boxes: ردیفِ y (آستانهٔ 10) → x داخلِ ردیف
        if len(final) > 1:
            ys = np.array([b[0][0][1] for b in final])
            order = np.argsort(ys, kind="stable")
            final = [final[i] for i in order]
            ys = ys[order]
            line_ids = np.concatenate(
                [[0], np.cumsum((np.diff(ys) >= 10).astype(np.int32))])
            xs = np.array([final[i][0][0][0] for i in range(len(final))])
            order2 = np.lexsort((xs, line_ids))
            final = [final[i] for i in order2]
        return final

    # ─────────────────────────── rec ───────────────────────────

    def _resize_norm(self, img: np.ndarray, img_w: int) -> np.ndarray:
        img_c, img_h, _ = self.rec_img_shape
        h, w = img.shape[:2]
        ratio = w / float(h)
        resized_w = img_w if math.ceil(img_h * ratio) > img_w \
            else int(math.ceil(img_h * ratio))
        resized = cv2.resize(img, (resized_w, img_h))
        resized = resized.astype("float32").transpose((2, 0, 1)) / 255.0
        resized -= 0.5
        resized /= 0.5
        pad = np.zeros((img_c, img_h, img_w), dtype=np.float32)
        pad[:, :, 0:resized_w] = resized
        return pad

    def _recognize(self, img_list):
        """خروجی: [(text, score), ...] به تعدادِ ورودی (CTC greedy)."""
        n = len(img_list)
        res = [("", 0.0)] * n
        width_list = [im.shape[1] / float(im.shape[0]) for im in img_list]
        indices = np.argsort(np.array(width_list))
        _, img_h, img_w = self.rec_img_shape
        for beg in range(0, n, self.rec_batch_num):
            end = min(n, beg + self.rec_batch_num)
            max_wh_ratio = img_w / float(img_h)
            for ino in range(beg, end):
                h, w = img_list[indices[ino]].shape[:2]
                max_wh_ratio = max(max_wh_ratio, w * 1.0 / h)
            batch_w = int(img_h * max_wh_ratio)
            batch = np.concatenate([
                self._resize_norm(img_list[indices[ino]], batch_w)[np.newaxis]
                for ino in range(beg, end)]).astype(np.float32)
            preds = self.rec(batch)
            preds_idx = preds.argmax(axis=2)
            preds_prob = preds.max(axis=2)
            for rno in range(preds_idx.shape[0]):
                tokens = preds_idx[rno]
                probs = preds_prob[rno]
                sel = np.ones(len(tokens), dtype=bool)
                sel[1:] = tokens[1:] != tokens[:-1]
                sel &= tokens != 0  # blank
                chars = [self.character[t] for t in tokens[sel]]
                text = "".join(chars)
                conf = float(np.mean(probs[sel])) if sel.any() else 0.0
                res[indices[beg + rno]] = (text, round(conf, 5))
        return res

    # ─────────────────────────── API ───────────────────────────

    @staticmethod
    def _get_rotate_crop(img: np.ndarray, points: np.ndarray) -> np.ndarray:
        """عینِ get_rotate_crop_image (پرسپکتیو + چرخشِ خطِ عمودی)."""
        pts = np.asarray(points, dtype=np.float32)
        w = int(np.linalg.norm(pts[0] - pts[1]))
        h = int(np.linalg.norm(pts[0] - pts[3]))
        if w < 1 or h < 1:
            return img
        std = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
        m = cv2.getPerspectiveTransform(pts, std)
        crop = cv2.warpPerspective(
            img, m, (w, h),
            borderMode=cv2.BORDER_REPLICATE, flags=cv2.INTER_CUBIC)
        if crop.shape[0] * 1.0 / max(1, crop.shape[1]) >= 1.5:
            crop = np.rot90(crop)
        return crop

    def _within_bounds(self, img: np.ndarray):
        """عینِ preprocess_img: max_side≤2000، min_side≥30 → (img, rh, rw)
        که ضربِ مختصات در (rh, rw) به تصویرِ اصلی برمیگردد. رزایزها
        به مضربِ ۳۲ گرد میشوند (عینِ reduce/increase_max_side)."""
        h, w = img.shape[:2]
        if max(h, w) > 2000:
            ratio = 2000.0 / max(h, w)
            resize_h = int(round((int(h * ratio)) / 32) * 32)
            resize_w = int(round((int(w * ratio)) / 32) * 32)
            if resize_w <= 0 or resize_h <= 0:
                raise ValueError("resize نامعتبر")
            img = cv2.resize(img, (resize_w, resize_h))
        if min(img.shape[:2]) < 30:
            h2, w2 = img.shape[:2]
            ratio2 = 30.0 / min(h2, w2)
            resize_h = int(round((int(h2 * ratio2)) / 32) * 32)
            resize_w = int(round((int(w2 * ratio2)) / 32) * 32)
            if resize_w <= 0 or resize_h <= 0:
                raise ValueError("resize نامعتبر")
            img = cv2.resize(img, (resize_w, resize_h))
        rh = h / float(img.shape[0])
        rw = w / float(img.shape[1])
        return img, rh, rw

    def ocr(self, image_bgr: np.ndarray):
        """خروجی: [ [box, (text, score)], ... ] یا None (خالی).

        خطِ کاملِ rapidocr: bounds-resize → vertical-padding → det →
        crop → rec → فیلترِ text_score → mapِ باکسها به تصویرِ اصلی."""
        if image_bgr is None or getattr(image_bgr, "size", 0) == 0:
            return None
        ori_h, ori_w = image_bgr.shape[:2]

        # ۱) resize در محدوده (عینِ Global.use_preprocess_img)
        work, rh, rw = self._within_bounds(image_bgr)

        # ۲) paddingِ عمودی برایِ کراپهایِ خیلی پهن (width_height_ratio=8)
        pad_top = 0
        h, w = work.shape[:2]
        if (w / float(max(1, h)) > 8.0) or h <= 30:
            new_h = max(int(w / 8.0), 30) * 2
            pad_top = int(abs(new_h - h) / 2)
            work = cv2.copyMakeBorder(
                work, pad_top, pad_top, 0, 0,
                cv2.BORDER_CONSTANT, value=(0, 0, 0))

        # ۳) det
        dets = self._detect(work)
        if not dets:
            return None

        # ۴) crop از تصویرِ کاری + rec (عینِ detect_and_crop)
        crops = [self._get_rotate_crop(work, b) for b, _s in dets]
        recs = self._recognize(crops)

        # ۵) خروجی + فیلتر + mapِ باکسها به تصویرِ اصلی
        lines = []
        for (box, _ds), (text, rscore) in zip(dets, recs):
            if not text.strip() or rscore < self.text_score:
                continue
            bx = np.asarray(box, dtype=np.float32).copy()
            bx[:, 1] -= pad_top
            bx[:, 0] *= rw
            bx[:, 1] *= rh
            bx[:, 0] = np.clip(bx[:, 0], 0, ori_w)
            bx[:, 1] = np.clip(bx[:, 1], 0, ori_h)
            lines.append([bx, (text, float(rscore))])
        return [lines] if lines else None
