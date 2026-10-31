#!/usr/bin/env python3
"""v1.14.69 — گیتِ «لاگ فقط دوتا».

Download/manga/ باید برایِ هر kind از لاگ فقط یک فایل داشته باشد
(manga.log.txt / manga_old.log.txt) و هیچ نسخهٔ شماره‌دارِ
«manga.log (N).txt» ساخته نشده باشد."""
import re
import subprocess
import sys


def sh(*a):
    return subprocess.run(list(a), capture_output=True, text=True,
                          errors="replace", timeout=60)


def norm(dn):
    s = dn.lower().strip()
    if not s.startswith("manga"):
        return None
    if ".log" not in s and not s.endswith(".txt"):
        return None
    s2 = re.sub(r" \(\d+\)", "", s)
    return "manga_old.log" if s2.startswith("manga_old") else "manga.log"


def main():
    r = sh("adb", "shell", "ls", "-1", "/sdcard/Download/manga/")
    names = [l.strip() for l in (r.stdout or "").splitlines() if l.strip()]
    if not names and (r.returncode != 0):
        print("[logs] ls failed:", (r.stderr or "")[:200])
        return 1
    logs = [n for n in names if norm(n)]
    dupish = [n for n in logs if re.search(r" \(\d+\)", n)]
    print("[logs] all files:", names)
    print("[logs] log-family:", logs)
    kinds = {}
    for n in logs:
        kinds.setdefault(norm(n), []).append(n)
    problems = []
    for k, v in sorted(kinds.items()):
        if len(v) > 1:
            problems.append(f"kind {k} has {len(v)} files: {v}")
    if dupish:
        problems.append(f"numbered duplicates present: {dupish}")
    if problems:
        print("[logs] GATE FAIL ✘: " + "; ".join(problems))
        return 1
    print(f"[logs] GATE PASS ✔ — log-family files: {sorted(set(logs))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
