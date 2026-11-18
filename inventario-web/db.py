"""Persistencia relacional para el proyecto de inventario.

SQLite permite practicar sin credenciales. En producción se usa el esquema
personal de Oracle FreeSQL mediante python-oracledb (modo thin).
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def stamp():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ident():
    return uuid.uuid4().hex[:12]


def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), 260_000)
    return f"pbkdf2_sha256${salt}${digest.hex()}"


def verify_password(password, stored):
    try:
        algorithm, salt, _ = stored.split("$", 2)
        if algorithm != "pbkdf2_sha256": return False
        return hmac.compare_digest(password_hash(password, salt), stored)
    except (ValueError, TypeError):
        return False


class Store:
    def __init__(self):
        self.mode = "oracle" if os.getenv("FREESQL_DSN") else "sqlite"
        self.sqlite_path = Path(os.getenv("INVENTARIO_SQLITE", ROOT / "inventario-demo.sqlite3"))
        if self.mode == "oracle" and not all(os.getenv(k) for k in ("FREESQL_USER", "FREESQL_PASSWORD")):
            raise RuntimeError("Faltan FREESQL_USER y FREESQL_PASSWORD")

    @contextmanager
    def connection(self):
        if self.mode == "oracle":
            import oracledb
            conn = oracledb.connect(
                user=os.environ["FREESQL_USER"],
                password=os.environ["FREESQL_PASSWORD"],
                dsn=os.environ["FREESQL_DSN"],
            )
        else:
            self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(self.sqlite_path)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def execute(self, conn, sql, params=None):
        cur = conn.cursor()
        cur.execute(sql, params or {})
        return cur

    def rows(self, conn, sql, params=None):
        cur = self.execute(conn, sql, params)
        names = [c[0].lower() for c in cur.description]
        result = []
        for row in cur.fetchall():
            result.append({key: float(value) if isinstance(value, Decimal) else value
                           for key, value in zip(names, row)})
        return result

    def one(self, conn, sql, params=None):
        return next(iter(self.rows(conn, sql, params)), None)

    def init(self):
        script = ROOT / ("schema.oracle.sql" if self.mode == "oracle" else "schema.sqlite.sql")
        statements = [s.strip() for s in script.read_text(encoding="utf-8").split(";") if s.strip()]
        with self.connection() as conn:
            for sql in statements:
                try:
                    self.execute(conn, sql)
                except Exception as exc:
                    if self.mode != "oracle" or "ORA-00955" not in str(exc):
                        raise
            count = self.one(conn, "SELECT COUNT(*) AS n FROM inv_categories")["n"]
            if count == 0:
                self.seed(conn)
            self.ensure_admin(conn)

    def ensure_admin(self, conn):
        username = os.getenv("INVENTARIO_ADMIN_USER", "").strip().lower()
        password = os.getenv("INVENTARIO_ADMIN_PASSWORD", "")
        if username and password and not self.one(conn, "SELECT id FROM inv_users WHERE username=:username", {"username":username}):
            self.execute(conn, """INSERT INTO inv_users (id,username,password_hash,role,active,created_at)
                VALUES (:id,:username,:password_hash,'admin',1,:created_at)""",
                {"id":ident(),"username":username,"password_hash":password_hash(password),"created_at":stamp()})

    def login(self, username, password):
        with self.connection() as conn:
            user = self.one(conn,"SELECT * FROM inv_users WHERE username=:username",{"username":str(username).strip().lower()})
            if not user or not user["active"] or not verify_password(str(password),user["password_hash"]):
                raise ValueError("Usuario o contraseña incorrectos")
            return {"id":user["id"],"username":user["username"],"role":user["role"]}

    def user_by_id(self, user_id):
        with self.connection() as conn:
            user = self.one(conn,"SELECT * FROM inv_users WHERE id=:id",{"id":user_id})
            return user if user and user["active"] else None

    def users(self):
        with self.connection() as conn:
            return self.rows(conn,"SELECT id,username,role,active,created_at FROM inv_users ORDER BY username")

    def create_user(self, data):
        username = str(data.get("username", "")).strip().lower()
        password = str(data.get("password", ""))
        role = str(data.get("role", "usuario"))
        if not re.fullmatch(r"[a-z0-9_.-]{3,60}",username):
            raise ValueError("Usuario: 3 a 60 letras minúsculas, números, punto, guion o guion bajo")
        if len(password) < 12: raise ValueError("La contraseña necesita al menos 12 caracteres")
        if role not in ("admin","usuario"): raise ValueError("Rol inválido")
        row = {"id":ident(),"username":username,"password_hash":password_hash(password),
               "role":role,"active":1,"created_at":stamp()}
        with self.connection() as conn:
            if self.one(conn,"SELECT id FROM inv_users WHERE username=:username",{"username":username}):
                raise ValueError("Ese usuario ya existe")
            self.execute(conn,"""INSERT INTO inv_users (id,username,password_hash,role,active,created_at)
                VALUES (:id,:username,:password_hash,:role,:active,:created_at)""",row)
        return {k:row[k] for k in ("id","username","role","active","created_at")}

    def update_user(self, user_id, data, actor_id):
        with self.connection() as conn:
            user = self.one(conn,"SELECT * FROM inv_users WHERE id=:id",{"id":user_id})
            if not user: raise ValueError("Usuario no encontrado")
            role = str(data.get("role",user["role"]))
            active = int(data.get("active",user["active"]))
            password = str(data.get("password", ""))
            if role not in ("admin","usuario") or active not in (0,1): raise ValueError("Rol o estado inválido")
            if password and len(password) < 12: raise ValueError("La contraseña necesita al menos 12 caracteres")
            if user_id == actor_id and (role != "admin" or not active):
                raise ValueError("No puedes quitarte tu propio acceso de administrador")
            if user["role"] == "admin" and (role != "admin" or not active):
                count = self.one(conn,"SELECT COUNT(*) AS n FROM inv_users WHERE role='admin' AND active=1")["n"]
                if count <= 1: raise ValueError("Debe quedar al menos un administrador activo")
            self.execute(conn,"UPDATE inv_users SET role=:role,active=:active WHERE id=:id",
                         {"id":user_id,"role":role,"active":active})
            if password:
                self.execute(conn,"UPDATE inv_users SET password_hash=:password_hash WHERE id=:id",
                             {"id":user_id,"password_hash":password_hash(password)})
            return {"id":user_id,"username":user["username"],"role":role,"active":active}

    def change_password(self, user_id, current, new):
        if len(new) < 12: raise ValueError("La contraseña nueva necesita al menos 12 caracteres")
        with self.connection() as conn:
            user = self.one(conn,"SELECT password_hash FROM inv_users WHERE id=:id",{"id":user_id})
            if not user or not verify_password(current,user["password_hash"]):
                raise ValueError("La contraseña actual es incorrecta")
            self.execute(conn,"UPDATE inv_users SET password_hash=:password_hash WHERE id=:id",
                         {"id":user_id,"password_hash":password_hash(new)})

    def seed(self, conn):
        categories = ["Tecnología", "Oficina", "Hogar", "Accesorios", "Audio"]
        suppliers = [
            ("Norte Digital", "compras@nortedigital.mx", "55 4100 2201"),
            ("Forma y Función", "hola@formayfuncion.mx", "55 4100 2202"),
            ("Suministros Atlas", "ventas@satlas.mx", "55 4100 2203"),
        ]
        customers = [
            ("Valeria Torres", "valeria@example.com", "55 3000 1001"),
            ("Estudio Nube", "compras@estudionube.mx", "55 3000 1002"),
            ("Diego Márquez", "diego@example.com", "55 3000 1003"),
            ("Oficina Prisma", "hola@prisma.mx", "55 3000 1004"),
        ]
        cat_ids, sup_ids, client_ids = [], [], []
        for name in categories:
            cid = ident(); cat_ids.append(cid)
            self.execute(conn, "INSERT INTO inv_categories (id,name) VALUES (:id,:name)", {"id": cid, "name": name})
        for name, email, phone in suppliers:
            sid = ident(); sup_ids.append(sid)
            self.execute(conn, "INSERT INTO inv_suppliers (id,name,email,phone) VALUES (:id,:name,:email,:phone)",
                         {"id":sid,"name":name,"email":email,"phone":phone})
        for name, email, phone in customers:
            cid = ident(); client_ids.append(cid)
            self.execute(conn, "INSERT INTO inv_customers (id,name,email,phone) VALUES (:id,:name,:email,:phone)",
                         {"id":cid,"name":name,"email":email,"phone":phone})
        products = [
            ("MacBook Stand", "MB-001", 0, 1, 480, 899, 32),
            ("Teclado mecánico", "TC-002", 0, 0, 690, 1299, 24),
            ("Mouse inalámbrico", "MS-003", 0, 0, 210, 499, 48),
            ("Hub USB-C 7 en 1", "HB-004", 0, 0, 530, 1090, 16),
            ("Monitor 27 pulgadas", "MN-005", 0, 2, 2550, 4199, 9),
            ("Libreta Studio", "LB-006", 1, 1, 65, 179, 84),
            ("Lámpara de escritorio", "LP-007", 2, 1, 360, 749, 21),
            ("Organizador modular", "OR-008", 1, 1, 140, 329, 37),
            ("Botella térmica", "BT-009", 2, 2, 190, 449, 45),
            ("Mochila urbana", "MC-010", 3, 2, 520, 1099, 18),
            ("Audífonos Studio", "AU-011", 4, 0, 920, 1799, 14),
            ("Altavoz compacto", "AL-012", 4, 0, 630, 1299, 12),
            ("Cargador 65W", "CG-013", 3, 0, 310, 699, 27),
            ("Webcam HD", "WC-014", 0, 0, 410, 899, 19),
            ("Base para celular", "BC-015", 3, 1, 90, 249, 52),
            ("Tapete de escritorio", "TP-016", 1, 1, 160, 389, 33),
        ]
        product_ids = []
        for name, sku, ci, si, cost, price, stock in products:
            pid = ident(); product_ids.append(pid)
            self.execute(conn, """INSERT INTO inv_products
                (id,sku,name,category_id,supplier_id,cost,price,stock,min_stock,active,created_at)
                VALUES (:id,:sku,:name,:category_id,:supplier_id,:cost,:price,:stock,:min_stock,1,:created_at)""",
                {"id":pid,"sku":sku,"name":name,"category_id":cat_ids[ci],"supplier_id":sup_ids[si],
                 "cost":cost,"price":price,"stock":stock,"min_stock":10,"created_at":stamp()})
            self.execute(conn, """INSERT INTO inv_movements
                (id,product_id,kind,quantity,note,created_at) VALUES (:id,:product_id,'entrada',:quantity,:note,:created_at)""",
                {"id":ident(),"product_id":pid,"quantity":stock,"note":"Inventario inicial de demostración","created_at":stamp()})
        demo_sales = [
            (client_ids[0], [(product_ids[1], 2), (product_ids[6], 1)]),
            (client_ids[1], [(product_ids[4], 1), (product_ids[5], 5)]),
            (client_ids[2], [(product_ids[10], 1), (product_ids[12], 2)]),
            (client_ids[3], [(product_ids[2], 3), (product_ids[7], 2)]),
            (client_ids[0], [(product_ids[9], 1), (product_ids[14], 2)]),
        ]
        for client_id, items in demo_sales:
            self.create_sale(conn, client_id, [{"product_id":pid,"quantity":qty} for pid,qty in items])

    def products(self, conn):
        return self.rows(conn, """SELECT p.*, c.name AS category, s.name AS supplier
            FROM inv_products p LEFT JOIN inv_categories c ON c.id=p.category_id
            LEFT JOIN inv_suppliers s ON s.id=p.supplier_id ORDER BY p.name""")

    def create_sale(self, conn, customer_id, items):
        if not self.one(conn, "SELECT id FROM inv_customers WHERE id=:id", {"id":customer_id}):
            raise ValueError("Selecciona un cliente válido")
        if not isinstance(items, list) or not items:
            raise ValueError("Agrega al menos un producto")
        sale_id = ident(); total = 0; gain = 0; prepared = []
        requested = {}
        for item in items:
            pid = item.get("product_id")
            qty = int(item.get("quantity", 0))
            if qty <= 0: raise ValueError("La cantidad debe ser mayor que cero")
            requested[pid] = requested.get(pid, 0) + qty
        for pid, qty in requested.items():
            product = self.one(conn, "SELECT * FROM inv_products WHERE id=:id", {"id":pid})
            if not product or product["stock"] < qty:
                raise ValueError("Producto inválido o existencias insuficientes")
            prepared.append((product, qty))
            total += product["price"] * qty
            gain += (product["price"] - product["cost"]) * qty
        invoice = "FAC-" + datetime.now().strftime("%y%m%d") + "-" + sale_id[:5].upper()
        self.execute(conn, """INSERT INTO inv_sales (id,invoice,customer_id,total,gain,created_at)
            VALUES (:id,:invoice,:customer_id,:total,:gain,:created_at)""",
            {"id":sale_id,"invoice":invoice,"customer_id":customer_id,"total":total,"gain":gain,"created_at":stamp()})
        for product, qty in prepared:
            self.execute(conn, """INSERT INTO inv_sale_items
                (id,sale_id,product_id,quantity,unit_price,unit_cost)
                VALUES (:id,:sale_id,:product_id,:quantity,:unit_price,:unit_cost)""",
                {"id":ident(),"sale_id":sale_id,"product_id":product["id"],"quantity":qty,
                 "unit_price":product["price"],"unit_cost":product["cost"]})
            cur = self.execute(conn, "UPDATE inv_products SET stock=stock-:q WHERE id=:id AND stock>=:q", {"q":qty,"id":product["id"]})
            if cur.rowcount != 1: raise ValueError("Existencias insuficientes; vuelve a cargar los datos")
            self.execute(conn, """INSERT INTO inv_movements (id,product_id,kind,quantity,note,created_at)
                VALUES (:id,:product_id,'venta',:quantity,:note,:created_at)""",
                {"id":ident(),"product_id":product["id"],"quantity":-qty,"note":invoice,"created_at":stamp()})
        return {"id":sale_id,"invoice":invoice,"total":round(total,2)}

    def bootstrap(self):
        with self.connection() as conn:
            products = self.products(conn)
            sales = self.rows(conn, """SELECT v.*, c.name AS customer FROM inv_sales v
                JOIN inv_customers c ON c.id=v.customer_id ORDER BY v.created_at DESC, v.invoice DESC""")
            moves = self.rows(conn, """SELECT m.*, p.name AS product FROM inv_movements m
                JOIN inv_products p ON p.id=m.product_id ORDER BY m.created_at DESC, m.id DESC""")
            return {
                "mode":self.mode,
                "products":products,
                "categories":self.rows(conn,"SELECT * FROM inv_categories ORDER BY name"),
                "suppliers":self.rows(conn,"SELECT * FROM inv_suppliers ORDER BY name"),
                "customers":self.rows(conn,"SELECT * FROM inv_customers ORDER BY name"),
                "sales":sales,
                "movements":moves[:80],
                "top_products":self.rows(conn,"""SELECT p.name, SUM(i.quantity) AS units,
                    SUM(i.quantity*i.unit_price) AS revenue, SUM(i.quantity*(i.unit_price-i.unit_cost)) AS profit
                    FROM inv_sale_items i JOIN inv_products p ON p.id=i.product_id
                    GROUP BY p.name ORDER BY units DESC""")[:8],
                "stats":{
                    "products":len(products),
                    "units":sum(p["stock"] for p in products),
                    "revenue":round(sum(s["total"] for s in sales),2),
                    "profit":round(sum(s["gain"] for s in sales),2),
                    "low_stock":sum(p["stock"] <= p["min_stock"] for p in products),
                    "sales":len(sales),
                },
            }

    def create(self, kind, data):
        with self.connection() as conn:
            if kind in ("categories","suppliers","customers"):
                name = str(data.get("name", "")).strip()
                if not name: raise ValueError("Escribe un nombre")
                table = "inv_" + kind
                row = {"id":ident(),"name":name,"email":str(data.get("email", "")).strip(),
                       "phone":str(data.get("phone", "")).strip()}
                if kind == "categories":
                    self.execute(conn, f"INSERT INTO {table} (id,name) VALUES (:id,:name)", row)
                else:
                    self.execute(conn, f"INSERT INTO {table} (id,name,email,phone) VALUES (:id,:name,:email,:phone)", row)
                return row
            if kind == "products":
                row = {"id":ident(),"sku":str(data.get("sku", "")).strip().upper(),
                       "name":str(data.get("name", "")).strip(),"category_id":data.get("category_id"),
                       "supplier_id":data.get("supplier_id"),"cost":float(data.get("cost",0)),
                       "price":float(data.get("price",0)),"stock":0,"min_stock":int(data.get("min_stock",10)),
                       "created_at":stamp()}
                if not row["sku"] or not row["name"] or row["cost"] < 0 or row["price"] <= 0:
                    raise ValueError("Completa SKU, nombre y precios válidos")
                self.execute(conn, """INSERT INTO inv_products
                    (id,sku,name,category_id,supplier_id,cost,price,stock,min_stock,active,created_at)
                    VALUES (:id,:sku,:name,:category_id,:supplier_id,:cost,:price,0,:min_stock,1,:created_at)""", row)
                return row
            if kind == "movements":
                pid = data.get("product_id"); qty = int(data.get("quantity",0)); direction = data.get("kind")
                product = self.one(conn,"SELECT * FROM inv_products WHERE id=:id",{"id":pid})
                if not product or qty <= 0 or direction not in ("entrada","salida"):
                    raise ValueError("Selecciona producto, tipo y cantidad válida")
                delta = qty if direction == "entrada" else -qty
                if product["stock"] + delta < 0: raise ValueError("Existencias insuficientes")
                row = {"id":ident(),"product_id":pid,"kind":direction,"quantity":delta,
                       "note":str(data.get("note", "")).strip(),"created_at":stamp()}
                self.execute(conn,"""INSERT INTO inv_movements (id,product_id,kind,quantity,note,created_at)
                    VALUES (:id,:product_id,:kind,:quantity,:note,:created_at)""",row)
                self.execute(conn,"UPDATE inv_products SET stock=stock+:q WHERE id=:id",{"q":delta,"id":pid})
                return row
            if kind == "sales":
                return self.create_sale(conn,data.get("customer_id"),data.get("items"))
            raise ValueError("Operación desconocida")

    def update_product(self, pid, data):
        with self.connection() as conn:
            row = self.one(conn,"SELECT * FROM inv_products WHERE id=:id",{"id":pid})
            if not row: raise ValueError("Producto no encontrado")
            values = {"id":pid,"name":str(data.get("name",row["name"])).strip(),
                      "sku":str(data.get("sku",row["sku"])).strip().upper(),
                      "cost":float(data.get("cost",row["cost"])),"price":float(data.get("price",row["price"])),
                      "min_stock":int(data.get("min_stock",row["min_stock"]))}
            if not values["name"] or not values["sku"] or values["cost"] < 0 or values["price"] <= 0:
                raise ValueError("Datos del producto inválidos")
            self.execute(conn,"""UPDATE inv_products SET name=:name,sku=:sku,cost=:cost,
                price=:price,min_stock=:min_stock WHERE id=:id""",values)
            return values

    def sale_detail(self, sale_id):
        with self.connection() as conn:
            sale = self.one(conn,"""SELECT v.*,c.name AS customer,c.email AS customer_email
                FROM inv_sales v JOIN inv_customers c ON c.id=v.customer_id WHERE v.id=:id""",{"id":sale_id})
            if not sale: raise ValueError("Factura no encontrada")
            sale["items"] = self.rows(conn,"""SELECT i.*,p.name AS product,p.sku FROM inv_sale_items i
                JOIN inv_products p ON p.id=i.product_id WHERE i.sale_id=:id ORDER BY p.name""",{"id":sale_id})
            return sale
