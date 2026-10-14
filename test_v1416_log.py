# -*- coding: utf-8 -*-
"""Test v1.14.16 file log: bridge._FullLog + _TeeStream + _log integration."""
import sys, os, time

REPO = "/home/z/manga-work/new-repo"
sys.path.insert(0, os.path.join(REPO, "android/app/src/main/python"))
sys.path.insert(0, REPO)

import bridge  # noqa: E402

import tempfile  # noqa: E402

td = tempfile.mkdtemp(prefix="mangalog")
job = {
    "done": False, "log": "", "error": None, "out_file": None,
    "images": [], "debug_images": [],
    "params": {"provider": "gemini", "fmt": "PDF", "debug": True,
               "tones": ["classic"]},
    "out": os.path.join(td, "out"), "out_file_path": os.path.join(td, "out", "m.pdf"),
    "cancel_requested": False, "cancelled": False,
    "files_dir": td, "_t0": time.time(),
}

# 1) open + params + tee writes + _log
bridge._FULLLOG.open(job["files_dir"])
bridge._FULLLOG.write(bridge._fulllog_params(job) + "\n")

tee = bridge._TeeStream(job)
long_line = "LONGLINE " * 80   # 720 chars — UI trims to 300, file must NOT
tee.write(long_line + "\n")
tee.write("PROG 42%|" + "=" * 200 + "\r")   # progress bar with \r
bridge._log(job, "✅ stage one done")
bridge._log(job, "[RapidOCR] some logging module line")
bridge._FULLLOG.close()

p = os.path.join(td, "manga.log")
log = open(p, encoding="utf-8").read()

assert log.startswith("=== Manga Translator v"), log[:120]
assert "v1.14.18" in log, "APP_VER missing"
assert "params: provider=gemini" in log
assert long_line.strip() in log, "long line was truncated in file!"
assert "PROG 42%|" in log, "progress line lost"
assert "\r" not in log, "CR not converted"
assert "✅ stage one done" in log, "_log() not mirrored to file"
assert "[RapidOCR] some logging module line" in log, "logging handler line missing"
assert "=== END — done=" not in log, "unexpected END (closed via close())"
print("FILE LOG OK — %d bytes" % os.path.getsize(p))
print("--- head ---")
print("\n".join(log.splitlines()[:4]))

# 2) rotation: second open must move previous to manga_old.log (v1.14.17+ naming)
bridge._FULLLOG.open(job["files_dir"])
assert os.path.isfile(os.path.join(td, "manga_old.log")), "rotation failed"
log2 = open(p, encoding="utf-8").read()
assert log2.count("=== Manga Translator") == 1
assert "stage one" not in log2, "old content leaked into new log"
print("ROTATION OK")

# 3) _run finally-path simulation: error job writes END footer
import threading
with bridge.STATE["lock"]:
    bridge.STATE["job"] = None

def _fake_run():
    j = dict(job)
    j["_t0"] = time.time()
    j["out"] = os.path.join(td, "out2")
    bridge._FULLLOG.open(j.get("files_dir"))
    bridge._FULLLOG.write(bridge._fulllog_params(j) + "\n")
    try:
        raise RuntimeError("boom test error")
    except BaseException:
        bridge._log(j, "❌ خطا:\nTraceback (most recent call last):\nRuntimeError: boom")
        with bridge.STATE["lock"]:
            j["done"] = True
            j["error"] = True
    finally:
        bridge._FULLLOG.write(
            "=== END — done=%s cancelled=%s error=%s — %.1fs ===\n"
            % (bool(j.get("done")), bool(j.get("cancelled")),
               bool(j.get("error")), time.time() - j.get("_t0", time.time())))
        bridge._FULLLOG.close()

_fake_run()
log3 = open(p, encoding="utf-8").read()
assert "=== END — done=True cancelled=False error=True — 0.0s ===" in log3
assert "RuntimeError: boom" in log3
print("ERROR FOOTER OK")
print("ALL FILE-LOG TESTS PASSED")
