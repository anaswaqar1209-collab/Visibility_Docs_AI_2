"""Start server, run tests, capture all output."""

import subprocess
import sys
import time
import signal

proc = subprocess.Popen(
    [sys.executable, "run.py"],
    cwd=r"C:\Users\X1\Desktop\Internship\Visibility_Docs_AI\backend",
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
)

time.sleep(12)

import httpx
try:
    c = httpx.Client(base_url="http://localhost:8000", timeout=30)
    r = c.get("/health")
    print("Health:", r.json(), flush=True)
except Exception as e:
    print(f"Health failed: {e}", flush=True)

output = []
while True:
    try:
        line = next(proc.stdout)
        output.append(line)
        print(line, end="", flush=True)
        if len(output) > 50:
            break
    except StopIteration:
        break

proc.terminate()
proc.wait()
