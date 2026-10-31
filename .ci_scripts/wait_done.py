#!/usr/bin/env python3
"""Wait for the in-app engine to finish (files/manga.log === END done=True).
Exits 0 on success, 1 on engine error/timeout. Prints the tail of the log."""
import subprocess
import sys
import time

DEADLINE_MIN = int(sys.argv[1]) if len(sys.argv) > 1 else 45


def read_log():
    r = subprocess.run(
        ["adb", "exec-out", "run-as", "com.amirwolf.mangatranslator",
         "cat", "files/manga.log"],
        capture_output=True, text=True, errors="replace", timeout=120)
    return r.stdout or ""


def main():
    deadline = time.time() + DEADLINE_MIN * 60
    last_len = 0
    while time.time() < deadline:
        try:
            log = read_log()
        except Exception as e:
            print(f"[wait] log read failed: {e}")
            time.sleep(20)
            continue
        if len(log) != last_len:
            last_len = len(log)
            tail = log.strip().splitlines()[-1:] or [""]
            print(f"[wait] {DEADLINE_MIN}min budget | tail: {tail[0][:120]}",
                  flush=True)
        if "=== END" in log and "done=True" in log:
            print("[wait] engine finished ✔")
            print(log[-4000:])
            return 0
        if "=== END" in log and "error=True" in log:
            print("[wait] engine reported ERROR ✘")
            print(log[-4000:])
            return 1
        time.sleep(20)
    print("[wait] TIMEOUT — engine never finished ✘")
    try:
        print(read_log()[-4000:])
    except Exception:
        pass
    return 1


if __name__ == "__main__":
    sys.exit(main())
