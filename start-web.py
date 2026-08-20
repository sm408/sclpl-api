#!/usr/bin/env python
"""SCLPLAPI Web Studio launcher.

Starts the FastAPI backend and the Vite dev server, then opens the browser.
"""

import os
import signal
import subprocess
import sys
import threading
import time


def _python() -> str:
    return sys.executable


def _run_uvicorn(db_path: str) -> subprocess.Popen:
    env = os.environ.copy()
    env["SCLPLAPI_DB"] = db_path
    return subprocess.Popen(
        [_python(), "-m", "uvicorn", "app.web.server:create_app", "--factory", "--host", "127.0.0.1", "--port", "8000"],
        cwd=os.path.dirname(os.path.abspath(__file__)),
        env=env,
    )


def _run_vite() -> subprocess.Popen:
    web_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
    return subprocess.Popen(
        ["pnpm", "vite", "--host"],
        cwd=web_dir,
    )


def _wait_for(url: str, timeout: int = 60) -> bool:
    import urllib.request

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=2)
            return True
        except Exception:
            time.sleep(0.5)
    return False


def main() -> int:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    sys.path.insert(0, script_dir)

    print()
    print(" =============================================")
    print("   SCLPLAPI Web Studio")
    print(" =============================================")
    print()
    print("  Starting backend...")
    backend = _run_uvicorn("data/sclplapi.db")

    print("  Starting frontend dev server...")
    frontend = _run_vite()

    try:
        if not _wait_for("http://127.0.0.1:8000/health", timeout=60):
            print("[WARN] Backend did not become ready in time.")
        if not _wait_for("http://127.0.0.1:5173", timeout=60):
            print("[WARN] Frontend did not become ready in time.")
    except KeyboardInterrupt:
        print("\n[INFO] Shutting down...")

    print()
    print("  Backend : http://127.0.0.1:8000")
    print("  Frontend: http://127.0.0.1:5173")
    print("  API docs: http://127.0.0.1:8000/docs")
    print()
    print("  Press Ctrl+C to stop both servers.")
    print()

    try:
        while True:
            time.sleep(1)
            if backend.poll() is not None and frontend.poll() is not None:
                break
    except KeyboardInterrupt:
        print("\n[INFO] Stopping servers...")
    finally:
        for proc in (backend, frontend):
            if proc and proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
