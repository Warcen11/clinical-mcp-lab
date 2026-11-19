"""Local diagnostic: python diagnose_sse.py (no MCP SDK required)."""
from __future__ import annotations

import socket
from urllib.error import HTTPError, URLError
from urllib.request import Request, ProxyHandler, build_opener

URL = "http://127.0.0.1:8000/sse"

try:
    with socket.create_connection(("127.0.0.1", 8000), timeout=2):
        print("TCP: порт 8000 принимает соединения")
except OSError as exc:
    print(f"TCP: порт 8000 не отвечает: {exc}")
    raise SystemExit(1)

# Explicitly forbid any OS/environment proxy for loopback.
opener = build_opener(ProxyHandler({}))
try:
    with opener.open(Request(URL, headers={"Accept": "text/event-stream"}), timeout=3) as response:
        print(f"HTTP без прокси: {response.status}")
        print(f"Content-Type: {response.headers.get('Content-Type', 'не задан')}")
        if response.status == 200 and "text/event-stream" in response.headers.get("Content-Type", ""):
            print("SSE: корректный поток открыт. Если Streamlit видит 503 — проверяйте прокси клиента.")
        else:
            print("SSE: отвечает не ожидаемый сервис; проверьте процесс, занявший порт 8000.")
except HTTPError as exc:
    print(f"HTTP без прокси: {exc.code} {exc.reason}")
    print("SSE: запрос дошёл до локального HTTP-сервиса, но сервер вернул ошибку.")
except URLError as exc:
    print(f"HTTP ошибка соединения: {exc.reason}")
except TimeoutError:
    print("HTTP: нет ответа в течение 3 секунд")
