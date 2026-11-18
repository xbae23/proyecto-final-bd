"""Servidor web del sistema de inventario y ventas.

Uso: python app.py. Con FREESQL_DSN configurado, toda operación usa Oracle.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
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
    def send_json(self, value, status=200, cookie=None):
        payload = json.dumps(value, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if cookie: self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(payload)

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length < 0 or length > 1_000_000: raise ValueError("Solicitud demasiado grande")
        return json.loads(self.rfile.read(length) or b"{}")

    def session_cookie(self, user):
        expiry = int(time.time()) + 12 * 3600
        payload = f"{user['id']}.{expiry}"
        key = os.environ["INVENTARIO_ADMIN_PASSWORD"].encode()
        signature = hmac.new(key,(payload+"."+user["password_hash"]).encode(),hashlib.sha256).hexdigest()
        token = f"{payload}.{signature}"
        secure = "; Secure" if self.headers.get("X-Forwarded-Proto") == "https" else ""
        return f"inventario_session={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age=43200{secure}"

    def current_user(self):
        try:
            cookies = dict(part.strip().split("=",1) for part in self.headers.get("Cookie", "").split(";") if "=" in part)
            user_id, expiry, signature = cookies.get("inventario_session", "").split(".",2)
            if int(expiry) <= time.time(): return None
            user = STORE.user_by_id(user_id)
            if not user: return None
            payload = f"{user_id}.{expiry}.{user['password_hash']}".encode()
            expected = hmac.new(os.environ["INVENTARIO_ADMIN_PASSWORD"].encode(),payload,hashlib.sha256).hexdigest()
            return user if hmac.compare_digest(signature,expected) else None
        except (ValueError, KeyError):
            return None

    def same_origin(self):
        origin = self.headers.get("Origin")
        return not origin or urlparse(origin).netloc == self.headers.get("Host")

    @staticmethod
    def public_user(user):
        return {"id":user["id"],"username":user["username"],"role":user["role"]}

    @staticmethod
    def visible_bootstrap(data, user):
        data["user"] = Handler.public_user(user)
        if user["role"] != "admin":
            for product in data["products"]: product.pop("cost",None)
            for sale in data["sales"]: sale.pop("gain",None)
            data["stats"].pop("profit",None)
            data.pop("top_products",None)
        return data

    def handle_request(self):
        path = urlparse(self.path).path
        if path.startswith("/api/"):
            try:
                if self.command in ("POST","PATCH") and not self.same_origin():
                    return self.send_json({"error":"Origen no permitido"},403)
                if self.command == "POST" and path == "/api/login":
                    data = self.read_json()
                    if not isinstance(data,dict): return self.send_json({"error":"Datos inválidos"},400)
                    try: identity = STORE.login(data.get("username",""),data.get("password",""))
                    except ValueError: return self.send_json({"error":"Usuario o contraseña incorrectos"},401)
                    user = STORE.user_by_id(identity["id"])
                    return self.send_json({"user":self.public_user(user)},cookie=self.session_cookie(user))
                user = self.current_user()
                if not user: return self.send_json({"error":"Inicia sesión para continuar"},401)
                if self.command == "POST" and path == "/api/logout":
                    return self.send_json({"ok":True},cookie="inventario_session=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0")
                if self.command == "GET" and path == "/api/me":
                    return self.send_json({"user":self.public_user(user)})
                if self.command == "GET" and path == "/api/bootstrap":
                    return self.send_json(self.visible_bootstrap(STORE.bootstrap(),user))
                if self.command == "GET" and path.startswith("/api/sales/"):
                    sale = STORE.sale_detail(path.rsplit("/",1)[-1])
                    if user["role"] != "admin":
                        sale.pop("gain",None)
                        for item in sale["items"]: item.pop("unit_cost",None)
                    return self.send_json(sale)
                if self.command == "GET" and path == "/api/users":
                    if user["role"] != "admin": return self.send_json({"error":"Solo administradores"},403)
                    return self.send_json(STORE.users())
                if self.command == "POST" and path == "/api/users":
                    if user["role"] != "admin": return self.send_json({"error":"Solo administradores"},403)
                    return self.send_json(STORE.create_user(self.read_json()),201)
                if self.command == "PATCH" and path.startswith("/api/users/"):
                    if user["role"] != "admin": return self.send_json({"error":"Solo administradores"},403)
                    return self.send_json(STORE.update_user(path.rsplit("/",1)[-1],self.read_json(),user["id"]))
                if self.command == "POST" and path == "/api/me/password":
                    data = self.read_json()
                    STORE.change_password(user["id"],str(data.get("current","")),str(data.get("new","")))
                    return self.send_json({"ok":True},cookie="inventario_session=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0")
                if self.command == "POST" and path in ("/api/categories","/api/suppliers","/api/customers","/api/products","/api/movements","/api/sales"):
                    if user["role"] != "admin" and path not in ("/api/customers","/api/sales"):
                        return self.send_json({"error":"Solo administradores"},403)
                    data = self.read_json()
                    return self.send_json(STORE.create(path.split("/")[2],data),201)
                if self.command == "PATCH" and path.startswith("/api/products/"):
                    if user["role"] != "admin": return self.send_json({"error":"Solo administradores"},403)
                    return self.send_json(STORE.update_product(path.rsplit("/",1)[-1],self.read_json()))
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
        self.send_header("X-Content-Type-Options","nosniff")
        self.send_header("Cache-Control","no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self): self.handle_request()
    def do_POST(self): self.handle_request()
    def do_PATCH(self): self.handle_request()


if __name__ == "__main__":
    host = os.getenv("INVENTARIO_HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8050"))
    if not all(os.getenv(k) for k in ("INVENTARIO_ADMIN_USER", "INVENTARIO_ADMIN_PASSWORD")):
        raise RuntimeError("Configura INVENTARIO_ADMIN_USER y INVENTARIO_ADMIN_PASSWORD")
    STORE.init()
    print(f"Inventario Studio: http://{host}:{port} | base: {STORE.mode}")
    ThreadingHTTPServer((host,port),Handler).serve_forever()
