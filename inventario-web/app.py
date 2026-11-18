"""Servidor web del sistema de inventario y ventas.

Uso: python app.py. Con FREESQL_DSN configurado, toda operación usa Oracle.
"""
from __future__ import annotations

import base64
import hmac
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from db import Store

ROOT = Path(__file__).resolve().parent
PUBLIC = ROOT / "static"
env_file = ROOT / ".env"
if env_file.exists():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())
STORE = Store()


class Handler(BaseHTTPRequestHandler):
    def send_json(self, value, status=200):
        payload = json.dumps(value, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def authorized(self):
        username = os.getenv("INVENTARIO_ADMIN_USER")
        password = os.getenv("INVENTARIO_ADMIN_PASSWORD")
        if not username or not password:
            return True
        raw = self.headers.get("Authorization", "")
        try:
            provided = base64.b64decode(raw.split(" ",1)[1]).decode("utf-8") if raw.startswith("Basic ") else ""
        except Exception:
            provided = ""
        return hmac.compare_digest(provided, f"{username}:{password}")

    def handle_request(self):
        if not self.authorized():
            self.send_response(401)
            self.send_header("WWW-Authenticate", 'Basic realm="Inventario Studio"')
            self.end_headers()
            return
        path = urlparse(self.path).path
        if path.startswith("/api/"):
            try:
                if self.command == "GET" and path == "/api/bootstrap":
                    return self.send_json(STORE.bootstrap())
                if self.command == "GET" and path.startswith("/api/sales/"):
                    return self.send_json(STORE.sale_detail(path.rsplit("/",1)[-1]))
                if self.command == "POST" and path in ("/api/categories","/api/suppliers","/api/customers","/api/products","/api/movements","/api/sales"):
                    length = int(self.headers.get("Content-Length", "0"))
                    if length > 1_000_000: return self.send_json({"error":"Solicitud demasiado grande"},413)
                    data = json.loads(self.rfile.read(length) or b"{}")
                    return self.send_json(STORE.create(path.split("/")[2],data),201)
                if self.command == "PATCH" and path.startswith("/api/products/"):
                    length = int(self.headers.get("Content-Length", "0"))
                    data = json.loads(self.rfile.read(length) or b"{}")
                    return self.send_json(STORE.update_product(path.rsplit("/",1)[-1],data))
                return self.send_json({"error":"Ruta no encontrada"},404)
            except (ValueError, TypeError, json.JSONDecodeError) as exc:
                return self.send_json({"error":str(exc)},400)
            except Exception as exc:
                print(f"Error de API: {exc}")
                return self.send_json({"error":"Error del servidor o de la base de datos"},500)
        if self.command != "GET": return self.send_json({"error":"Método no permitido"},405)
        file = PUBLIC / (path.lstrip("/") or "index.html")
        if not file.is_file() or not file.resolve().is_relative_to(PUBLIC.resolve()):
            file = PUBLIC / "index.html"
        mime = {".html":"text/html", ".css":"text/css", ".js":"text/javascript", ".svg":"image/svg+xml"}.get(file.suffix,"application/octet-stream")
        body = file.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type",mime+"; charset=utf-8")
        self.send_header("Content-Length",str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self): self.handle_request()
    def do_POST(self): self.handle_request()
    def do_PATCH(self): self.handle_request()


if __name__ == "__main__":
    host = os.getenv("INVENTARIO_HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8050"))
    if host not in ("127.0.0.1", "localhost") and not all(
        os.getenv(k) for k in ("INVENTARIO_ADMIN_USER", "INVENTARIO_ADMIN_PASSWORD")
    ):
        raise RuntimeError("Configura INVENTARIO_ADMIN_USER y INVENTARIO_ADMIN_PASSWORD para acceso público")
    STORE.init()
    print(f"Inventario Studio: http://{host}:{port} | base: {STORE.mode}")
    ThreadingHTTPServer((host,port),Handler).serve_forever()
