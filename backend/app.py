"""ShopEase API: a small e-commerce backend built for the DevOps course.

Run it on your laptop:   python app.py      then open http://localhost:5000
Run it on a server:      gunicorn -w 2 -b 127.0.0.1:5000 wsgi:app
"""
import json
import logging
import os
import re
import socket
import threading
import time

from flask import Flask, g, jsonify, request, send_from_directory

import db

APP_VERSION = os.getenv("APP_VERSION", "1.0.0")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")
ORDER_QUEUE_URL = os.getenv("ORDER_QUEUE_URL", "")
FRONTEND_DIR = os.path.abspath(os.getenv("FRONTEND_DIR", os.path.join(os.path.dirname(__file__), "..", "frontend")))
ORDER_STATUSES = ["PLACED", "PAID", "SHIPPED", "DELIVERED", "CANCELLED"]
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("shopease")

# ---------------------------------------------------------------- metrics
# A tiny Prometheus exporter, so /metrics works without extra libraries.
_metrics_lock = threading.Lock()
_requests = {}        # (method, route, status) -> count
_durations = {}       # route -> [sum_seconds, count]
_orders = {"count": 0, "value": 0}


def _record(method, route, status, seconds):
    with _metrics_lock:
        key = (method, route, str(status))
        _requests[key] = _requests.get(key, 0) + 1
        d = _durations.setdefault(route, [0.0, 0])
        d[0] += seconds
        d[1] += 1


def create_app(serve_frontend=None):
    app = Flask(__name__, static_folder=None)
    app.json.sort_keys = False
    if serve_frontend is None:
        serve_frontend = os.getenv("SERVE_FRONTEND", "0") == "1"

    if os.getenv("AUTO_INIT_DB", "1") == "1":
        db.init_db()

    # ------------------------------------------------------------ helpers
    def conn():
        if "conn" not in g:
            g.conn = db.connect()
        return g.conn

    @app.teardown_appcontext
    def close_conn(_exc):
        c = g.pop("conn", None)
        if c is not None:
            c.close()

    @app.before_request
    def start_timer():
        g.start = time.time()

    @app.after_request
    def log_request(response):
        route = request.url_rule.rule if request.url_rule else "other"
        seconds = time.time() - g.get("start", time.time())
        _record(request.method, route, response.status_code, seconds)
        if route.startswith("/api"):
            log.info("%s %s %s %.1fms", request.method, request.path, response.status_code, seconds * 1000)
        return response

    def error(message, status):
        return jsonify({"error": message}), status

    def require_admin():
        if not ADMIN_TOKEN:
            return error("Admin is disabled. Set the ADMIN_TOKEN environment variable.", 403)
        if request.headers.get("X-Admin-Token", "") != ADMIN_TOKEN:
            return error("Wrong or missing admin token.", 401)
        return None

    def order_with_items(order_id):
        order = db.query_one(conn(), "SELECT * FROM orders WHERE id = ?", (order_id,))
        if order:
            order["items"] = db.query_all(
                conn(), "SELECT product_id, product_name, unit_price, qty FROM order_items WHERE order_id = ? ORDER BY id", (order_id,))
        return order

    # ------------------------------------------------------------ health
    @app.get("/api/health")
    def health():
        try:
            db.query_one(conn(), "SELECT 1 AS ok")
            db_status = "ok"
        except Exception as exc:  # noqa: BLE001
            log.error("health check: database error: %s", exc)
            db_status = "error"
        body = {"status": "ok" if db_status == "ok" else "error", "database": db_status,
                "engine": db.ENGINE, "version": APP_VERSION, "server": socket.gethostname()}
        return jsonify(body), (200 if db_status == "ok" else 503)

    # ------------------------------------------------------------ products
    @app.get("/api/categories")
    def categories():
        rows = db.query_all(conn(), "SELECT DISTINCT category FROM products ORDER BY category")
        return jsonify([r["category"] for r in rows])

    @app.get("/api/products")
    def list_products():
        statement = "SELECT * FROM products WHERE 1 = 1"
        params = []
        category = request.args.get("category", "").strip()
        search = request.args.get("q", "").strip()
        if category:
            statement += " AND category = ?"
            params.append(category)
        if search:
            statement += " AND (LOWER(name) LIKE ? OR LOWER(description) LIKE ?)"
            params += [f"%{search.lower()}%", f"%{search.lower()}%"]
        statement += " ORDER BY id"
        return jsonify(db.query_all(conn(), statement, tuple(params)))

    @app.get("/api/products/<int:product_id>")
    def get_product(product_id):
        product = db.query_one(conn(), "SELECT * FROM products WHERE id = ?", (product_id,))
        if not product:
            return error("Product not found.", 404)
        return jsonify(product)

    # ------------------------------------------------------------ orders
    @app.post("/api/orders")
    def create_order():
        data = request.get_json(silent=True) or {}
        customer = data.get("customer") or {}
        items = data.get("items") or []

        name = str(customer.get("name", "")).strip()
        email = str(customer.get("email", "")).strip().lower()
        phone = re.sub(r"[^0-9+]", "", str(customer.get("phone", "")))
        address = str(customer.get("address", "")).strip()
        problems = []
        if len(name) < 2:
            problems.append("name")
        if not EMAIL_RE.match(email):
            problems.append("email")
        if len(re.sub(r"\D", "", phone)) < 10:
            problems.append("phone")
        if len(address) < 10:
            problems.append("address")
        if problems:
            return error("Please check: " + ", ".join(problems) + ".", 400)
        if not isinstance(items, list) or not items or len(items) > 20:
            return error("Your cart is empty or too large.", 400)

        wanted = {}
        for item in items:
            try:
                pid, qty = int(item["product_id"]), int(item["qty"])
            except (KeyError, TypeError, ValueError):
                return error("Each item needs a product_id and a qty.", 400)
            if qty < 1 or qty > 10:
                return error("Quantity must be between 1 and 10.", 400)
            wanted[pid] = wanted.get(pid, 0) + qty

        c = conn()
        lock = " FOR UPDATE" if db.ENGINE == "mysql" else ""
        try:
            if db.ENGINE == "sqlite":
                c.execute("BEGIN IMMEDIATE")
            lines, total = [], 0
            for pid, qty in wanted.items():
                product = db.query_one(c, "SELECT id, name, price, stock FROM products WHERE id = ?" + lock, (pid,))
                if not product:
                    c.rollback()
                    return error(f"Product {pid} does not exist.", 400)
                if product["stock"] < qty:
                    c.rollback()
                    return error(f"Sorry, only {product['stock']} left of {product['name']}.", 409)
                db.execute(c, "UPDATE products SET stock = stock - ? WHERE id = ?", (qty, pid))
                lines.append((product, qty))
                total += product["price"] * qty   # prices always come from the database, never the browser
            order_id, _ = db.execute(
                c, "INSERT INTO orders (customer_name, email, phone, address, total) VALUES (?, ?, ?, ?, ?)",
                (name, email, phone, address, total))
            for product, qty in lines:
                db.execute(c, "INSERT INTO order_items (order_id, product_id, product_name, unit_price, qty) VALUES (?, ?, ?, ?, ?)",
                           (order_id, product["id"], product["name"], product["price"], qty))
            c.commit()
        except Exception:
            c.rollback()
            raise

        with _metrics_lock:
            _orders["count"] += 1
            _orders["value"] += total
        log.info("order %s placed: %s items, total Rs %s", order_id, sum(wanted.values()), total)
        send_to_queue(order_id, email, total)
        return jsonify({"id": order_id, "total": total, "status": "PLACED"}), 201

    @app.get("/api/orders/<int:order_id>")
    def get_order(order_id):
        email = request.args.get("email", "").strip().lower()
        order = order_with_items(order_id)
        if not order or order["email"] != email:
            return error("No order found with that number and email.", 404)
        return jsonify(order)

    # ------------------------------------------------------------ admin
    @app.get("/api/admin/orders")
    def admin_orders():
        denied = require_admin()
        if denied:
            return denied
        orders = db.query_all(conn(), "SELECT * FROM orders ORDER BY id DESC LIMIT 200")
        return jsonify(orders)

    @app.patch("/api/admin/orders/<int:order_id>")
    def admin_update_order(order_id):
        denied = require_admin()
        if denied:
            return denied
        status = str((request.get_json(silent=True) or {}).get("status", "")).upper()
        if status not in ORDER_STATUSES:
            return error("Status must be one of: " + ", ".join(ORDER_STATUSES), 400)
        c = conn()
        order = order_with_items(order_id)
        if not order:
            return error("Order not found.", 404)
        if status == "CANCELLED" and order["status"] != "CANCELLED":
            for item in order["items"]:   # put the items back in stock
                db.execute(c, "UPDATE products SET stock = stock + ? WHERE id = ?", (item["qty"], item["product_id"]))
        db.execute(c, "UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
        c.commit()
        log.info("order %s status changed to %s", order_id, status)
        return jsonify(order_with_items(order_id))

    # ------------------------------------------------------------ metrics
    @app.get("/metrics")
    def metrics():
        lines = ["# HELP shopease_http_requests_total HTTP requests by method, route and status.",
                 "# TYPE shopease_http_requests_total counter"]
        with _metrics_lock:
            for (method, route, status), n in sorted(_requests.items()):
                lines.append(f'shopease_http_requests_total{{method="{method}",route="{route}",status="{status}"}} {n}')
            lines += ["# HELP shopease_http_request_duration_seconds Time spent answering requests.",
                      "# TYPE shopease_http_request_duration_seconds summary"]
            for route, (total, count) in sorted(_durations.items()):
                lines.append(f'shopease_http_request_duration_seconds_sum{{route="{route}"}} {total:.6f}')
                lines.append(f'shopease_http_request_duration_seconds_count{{route="{route}"}} {count}')
            lines += ["# HELP shopease_orders_total Orders placed since the API started.",
                      "# TYPE shopease_orders_total counter", f"shopease_orders_total {_orders['count']}",
                      "# HELP shopease_order_value_rupees_total Value of orders placed since the API started.",
                      "# TYPE shopease_order_value_rupees_total counter", f"shopease_order_value_rupees_total {_orders['value']}"]
        low = db.query_one(conn(), "SELECT COUNT(*) AS n FROM products WHERE stock < 5")["n"]
        lines += ["# HELP shopease_products_low_stock Products with fewer than 5 in stock.",
                  "# TYPE shopease_products_low_stock gauge", f"shopease_products_low_stock {low}"]
        return "\n".join(lines) + "\n", 200, {"Content-Type": "text/plain; version=0.0.4"}

    # ------------------------------------------------------------ website (laptop mode only)
    if serve_frontend:
        @app.get("/")
        def home():
            return send_from_directory(FRONTEND_DIR, "index.html")

        @app.get("/<path:path>")
        def static_files(path):
            return send_from_directory(FRONTEND_DIR, path)

    return app


def send_to_queue(order_id, email, total):
    """Module 5: if ORDER_QUEUE_URL is set, tell the order worker about the new order via Amazon SQS."""
    if not ORDER_QUEUE_URL:
        return
    try:
        import boto3
        sqs = boto3.client("sqs", region_name=os.getenv("AWS_REGION", "ap-south-1"))
        sqs.send_message(QueueUrl=ORDER_QUEUE_URL,
                         MessageBody=json.dumps({"order_id": order_id, "email": email, "total": total}))
        log.info("order %s sent to SQS", order_id)
    except Exception as exc:  # noqa: BLE001  - the order is already saved; never fail the customer
        log.error("could not send order %s to SQS: %s", order_id, exc)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    create_app(serve_frontend=True).run(host="0.0.0.0", port=port, debug=False)
