#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.14.518 — بنچِ سرعتِ استخراج + پاکسازی رویِ شبیه‌سازِ واقعیِ اندروید.

همان سه عکسِ بنچِ PC (img6 / img2 / 4e2e77) با همان تنظیماتِ
scripts/bench_speed_gh.py (clean_only + lama-manga + fake_test) از
طریقِ UI واقعیِ اپ (دکمهٔ «شروع ترجمه» با tap_run) اجرا میشوند و از
manga.log اینها پارس میشود:

  • «[+] متن استخراج شد: N ناحیه | زمانِ استخراج: X ثانیه | موتور: …»
  • «[⚡] OCR: N ناحیه | میانگینِ Xms»
  • «[+] پاکسازی: X ثانیه با …»
  • شمارِ «خطای موتور OCR» (باید صفر باشد)
  • wall-clock کل هر عکس (tap → === END)

اعداد مستقیماً با رانِ speed-testِ PC قابلِ مقایسه‌اند (همان عکسها،
همان تنظیمات). پیش‌نیازها (قبل از این اسکریپت در workflow):
APK نصب، مدلهای RT-DETR/LaMa/rapidocr روی filesDir، emulator بوت.
"""
import json
import os
import re
import subprocess
import sys
import time

PKG = "com.amirwolf.mangatranslator"
ACT = PKG + "/.MainActivity"
IMAGES = ["img6.jpg", "img2.webp", "4e2e77.webp"]
OUT_JSON = os.environ.get("BENCH_OUT", "/tmp/android_bench.json")
CI = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(CI)
WAIT_MIN = int(os.environ.get("BENCH_WAIT_MIN", "20"))


def sh(*a, timeout=180):
    return subprocess.run(list(a), capture_output=True, text=True,
                          errors="replace", timeout=timeout)


def run_as(*args, timeout=120):
    return sh("adb", "exec-out", "run-as", PKG, *args, timeout=timeout)


def set_prefs(inp_name):
    """همان prefs بنچِ PC: clean_only + lama-manga + PDF + fake."""
    xml = (
        "<?xml version='1.0' encoding='utf-8' standalone='yes' ?>\n"
        "<map>\n"
        f"    <string name=\"inp_upload_path\">/data/user/0/{PKG}/files/"
        f"{inp_name}</string>\n"
        "    <string name=\"fake_test\">true</string>\n"
        "    <string name=\"clean_only\">true</string>\n"
        "    <string name=\"web_debug\">true</string>\n"
        "    <string name=\"clean_method\">lama-manga</string>\n"
        "    <string name=\"out_fmt\">PDF</string>\n"
        "    <string name=\"reader\">rtl</string>\n"
        "    <boolean name=\"battery_asked\" value=\"true\" />\n"
        "    <boolean name=\"viewer_hint_v3\" value=\"true\" />\n"
        "</map>\n"
    )
    with open("/tmp/bench_prefs.xml", "w", encoding="utf-8") as f:
        f.write(xml)
    sh("adb", "push", "/tmp/bench_prefs.xml", "/data/local/tmp/bench_prefs.xml")
    sh("adb", "shell",
       f"run-as {PKG} sh -c 'mkdir -p /data/user/0/{PKG}/shared_prefs && "
       f"cat /data/local/tmp/bench_prefs.xml > "
       f"/data/user/0/{PKG}/shared_prefs/manga_settings.xml'")


def read_log():
    r = run_as("cat", "files/manga.log", timeout=60)
    return r.stdout or ""


def parse_metrics(log):
    m = {}
    mt = re.search(r"متن استخراج شد:\s*(\d+) ناحیه\s*\|\s*"
                   r"زمانِ استخراج:\s*([\d.]+)\s*ثانیه\s*\|\s*موتور:\s*(\S+)",
                   log)
    if mt:
        m["regions"] = int(mt.group(1))
        m["extract_s"] = float(mt.group(2))
        m["engine"] = mt.group(3)
    oc = re.search(r"\[⚡\] OCR:\s*(\d+) ناحیه\s*\|\s*میانگینِ\s*(\d+)ms",
                   log)
    if oc:
        m["ocr_avg_ms"] = int(oc.group(2))
    # فرمتِ اندروید: «[+] پاکسازیِ برش‌ها (خالص): N برش | lama=A
    # bgfill=B gradfill=C telea=D skip=E | X.Ys» — تفکیکِ روشها ریشهٔ
    # کندیِ گوشی (برشهایِ LaMa) را نشان میدهد.
    cl = re.search(
        r"پاکسازیِ برش‌ها \(خالص\):\s*(\d+) برش\s*\|"
        r"\s*lama=(\d+)\s+bgfill=(\d+)\s+gradfill=(\d+)"
        r"\s+telea=(\d+)\s+skip=(\d+)\s*\|\s*([\d.]+)s", log)
    if cl:
        m["clean_s"] = float(cl.group(7))
        m["clean_crops"] = int(cl.group(1))
        m["clean_lama"] = int(cl.group(2))
        m["clean_bgfill"] = int(cl.group(3))
        m["clean_gradfill"] = int(cl.group(4))
    else:
        # فرمتِ PC: «[+] پاکسازی: X ثانیه با …»
        cl2 = re.search(r"\[\+\] پاکسازی:\s*([\d.]+)\s*ثانیه", log)
        if cl2:
            m["clean_s"] = float(cl2.group(1))
    m["engine_errors"] = len(re.findall(r"خطای موتور OCR", log))
    m["opencv_fallbacks"] = len(
        re.findall(r"'OpenCV':\s*[1-9]", log))
    return m


def main():
    report = {"per_image": {}, "engine": "", "engine_errors": 0}
    fail = False
    for name in IMAGES:
        stem = os.path.splitext(name)[0]
        src = os.path.join(ROOT, "ci_imgs", name)
        if not os.path.isfile(src):
            print(f"[skip] {name} not found")
            continue
        print(f"\n══════════ [{name}] ══════════", flush=True)
        sh("adb", "shell", "am", "force-stop", PKG)
        time.sleep(3)
        sh("adb", "push", src, f"/data/local/tmp/bench_{name}")
        sh("adb", "shell",
           f"run-as {PKG} sh -c 'cat /data/local/tmp/bench_{name} > "
           f"/data/user/0/{PKG}/files/{name}'")
        sh("adb", "shell", "rm", "-f", f"/data/local/tmp/bench_{name}")
        set_prefs(name)
        sh("adb", "shell", f"run-as {PKG} sh -c ': > files/manga.log'")
        sh("adb", "logcat", "-c")
        sh("adb", "shell", "am", "start", "-W", "-n", ACT)
        time.sleep(12)
        if subprocess.call([sys.executable,
                            os.path.join(CI, "tap_run.py")]) != 0:
            print(f"::error::{name} — tap_run failed")
            log = read_log()
            print(log[-2500:])
            report["per_image"][name] = {"tap_run": "fail"}
            fail = True
            continue
        t0 = time.time()
        if subprocess.call([sys.executable,
                            os.path.join(CI, "wait_done.py"),
                            str(WAIT_MIN)]) != 0:
            print(f"::error::{name} — engine did not finish")
            log = read_log()
            print(log[-2500:])
            report["per_image"][name] = {"finished": "timeout"}
            fail = True
            continue
        wall = time.time() - t0
        log = read_log()
        m = parse_metrics(log)
        m["wall_s"] = round(wall, 1)
        # PDF گیت
        r = run_as("cat", f"files/work/out/{stem}.pdf", timeout=90)
        pdf_ok = len(r.stdout or "") > 8000
        m["pdf_ok"] = bool(pdf_ok)
        report["per_image"][name] = m
        report["engine"] = m.get("engine", report["engine"])
        report["engine_errors"] += m.get("engine_errors", 0)
        print(f"[BENCH] {name}: wall={wall:.1f}s | "
              f"extract={m.get('extract_s', '?')}s/{m.get('regions', '?')}منطقه "
              f"| ocr_avg={m.get('ocr_avg_ms', '—')}ms | "
              f"clean={m.get('clean_s', '?')}s"
              f" (lama={m.get('clean_lama', '?')}"
              f"/grad={m.get('clean_gradfill', '?')}"
              f"/bg={m.get('clean_bgfill', '?')}"
              f" از {m.get('clean_crops', '?')}) | "
              f"engine_errors={m.get('engine_errors', '?')} | "
              f"pdf={'OK' if pdf_ok else 'MISSING'}", flush=True)
        if not m.get("regions"):
            print(f"::error::{name} — no regions extracted")
            fail = True
        if m.get("engine_errors"):
            print(f"::error::{name} — engine errors: {m['engine_errors']}")
            fail = True
        if not pdf_ok:
            print(f"::error::{name} — output PDF missing/too small")
            fail = True

    print("\n══════════ جدولِ بنچِ اندروید (همان عکسهایِ بنچِ PC) ══════════",
          flush=True)
    tot_e = sum(v.get("extract_s", 0) for v in report["per_image"].values()
                if isinstance(v, dict))
    tot_c = sum(v.get("clean_s", 0) for v in report["per_image"].values()
                if isinstance(v, dict))
    for name, v in report["per_image"].items():
        if not isinstance(v, dict) or "wall_s" not in v:
            print(f"  {name:14s}: FAILED", flush=True)
            continue
        print(f"  {name:14s}: wall={v.get('wall_s')}s | "
              f"extract={v.get('extract_s')}s/{v.get('regions')} | "
              f"clean={v.get('clean_s')}s "
              f"(lama={v.get('clean_lama', '—')}/"
              f"grad={v.get('clean_gradfill', '—')}/"
              f"bg={v.get('clean_bgfill', '—')}) | "
              f"err={v.get('engine_errors')}", flush=True)
    print(f"  موتور: {report['engine'] or '?'} | "
          f"مجموعِ استخراج: {tot_e:.1f}s | مجموعِ پاکسازی: {tot_c:.1f}s | "
          f"ارورهای موتور: {report['engine_errors']}", flush=True)
    print(f"\n[BENCH-RESULT] {'PASS ✅' if not fail else 'FAIL ❌'}", flush=True)

    try:
        with open(OUT_JSON, "w") as f:
            json.dump(report, f, ensure_ascii=False, indent=1)
    except Exception:
        pass
    sys.exit(0 if not fail else 3)


if __name__ == "__main__":
    main()
