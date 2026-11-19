"""One-command dev launcher: python run.py (Windows/Linux/macOS)."""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main() -> int:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    server_cmd = [sys.executable, "-m", "clinical_mcp.network.server"]
    ui_cmd = [sys.executable, "-m", "streamlit", "run", str(ROOT / "app.py"),
              "--server.address", "127.0.0.1", "--server.port", "8501"]
    def port_is_listening() -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.2)
            return sock.connect_ex(("127.0.0.1", 8000)) == 0

    if port_is_listening():
        print("Ошибка: порт 8000 уже занят другим процессом. "
              "Остановите старый SSE-сервер и запустите python run.py заново.", file=sys.stderr)
        return 1

    server = subprocess.Popen(server_cmd, cwd=ROOT, env=env)
    try:
        deadline = time.monotonic() + 10.0
        while not port_is_listening():
            if server.poll() is not None:
                print(f"Ошибка: SSE-сервер завершился с кодом {server.returncode}. "
                      "Смотрите traceback выше.", file=sys.stderr)
                return 1
            if time.monotonic() >= deadline:
                print("Ошибка: SSE-сервер не открыл порт 8000 за 10 секунд.", file=sys.stderr)
                return 1
            time.sleep(0.1)

        print("SSE-сервер слушает 127.0.0.1:8000; запускаем Streamlit...", flush=True)
        ui = subprocess.Popen(ui_cmd, cwd=ROOT, env=env)
        try:
            warned_sse_stopped = False
            while ui.poll() is None:
                if server.poll() is not None and not warned_sse_stopped:
                    print(
                        "Предупреждение: SSE-сервер остановился. "
                        "Streamlit продолжает работать; инструменты SSE временно недоступны. "
                        "Перезапустите python run.py, чтобы снова поднять SSE-сервер.",
                        file=sys.stderr,
                        flush=True,
                    )
                    warned_sse_stopped = True
                time.sleep(0.4)
            return ui.returncode or 0
        except KeyboardInterrupt:
            return 0
        finally:
            if ui.poll() is None:
                ui.terminate()
                try:
                    ui.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    ui.kill()
    finally:
        if server.poll() is None:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()


if __name__ == "__main__":
    raise SystemExit(main())
