import os
import re
import json
import html
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# =========================
# CONFIG
# =========================

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
PARTS_GROUP_ID = int(os.getenv("PARTS_GROUP_ID", "0"))
RETURNS_GROUP_ID = int(os.getenv("RETURNS_GROUP_ID", "0"))
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").rstrip("/")
DB_PATH = os.getenv("DB_PATH", "bot.db")
PORT = int(os.getenv("PORT", "10000"))

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")
if not WEBHOOK_URL:
    raise RuntimeError("WEBHOOK_URL is not set")
if not PARTS_GROUP_ID:
    raise RuntimeError("PARTS_GROUP_ID is not set")
if not RETURNS_GROUP_ID:
    raise RuntimeError("RETURNS_GROUP_ID is not set")

DESTINATIONS: Dict[str, Dict[str, str]] = {
    "dest_1": {
        "button": "1. ТЕС ТРАКС ОДЕСА",
        "title": "ТЕС ТРАКС ОДЕСА",
        "details": 'ООО "ТЕС ТРАКС ОДЕСА"\nЕГРПОУ: 40199838\nАдрес: 65031, г. Одесса, ул. Киевское шоссе, д. 5',
    },
    "dest_2": {
        "button": "2. Технопартс",
        "title": "Технопартс",
        "details": "Компания Технопартс\nЕГРПОУ: 39489921\nАдрес: Кременчуг, ул. Киевская, 64",
    },
    "dest_3": {
        "button": "3. ТРАК ДРАЙВ",
        "title": "ТРАК ДРАЙВ",
        "details": 'ООО "ТРАК ДРАЙВ"\nЕГРПОУ: 37913687\nАдрес: Балтская дорога, 148, Одесса, Одесская область',
    },
    "dest_4": {
        "button": "4. Бузовая ДАФ",
        "title": "Бузовая ДАФ",
        "details": "Бузовая ДАФ\nАдрес: Киевская обл., с. Бузовая, ДАФ",
    },
    "dest_5": {
        "button": "5. Луцк ДПФ ТЕХ НП 24",
        "title": "Луцк ДПФ ТЕХ НП 24",
        "details": 'ТОВ "ДПФ ТЕХ"\nЕГРПОУ: 42224698\nАдрес доставки: г. Луцк, Новая почта №24 до 30 кг',
    },
    "dest_6": {
        "button": "6. Жидичин ДПФ ТЕХ",
        "title": "Жидичин ДПФ ТЕХ",
        "details": "Жидичин / Луцк ДПФ ТЕХ\nЕГРПОУ: 42224698\nАдрес: улица 17-го Сентября, д. 89, с. Жидичин, Волынская область",
    },
    "dest_7": {
        "button": "7. Ровно Ренамакс",
        "title": "Ровно Ренамакс",
        "details": "Ровно, Ренамакс\nЕГРПОУ: 37802144\nОписание: Грузовое СТО Ровно 339 км / TIR service RENAMAX - Ренамакс\nАдрес сервиса: https://maps.app.goo.gl/ckdLNghBNB1xwAjv6",
    },
    "dest_8": {
        "button": "8. ТРАК Центр Днепр",
        "title": "ТРАК Центр Днепр",
        "details": "ТРАК Центр Днепр\nЕГРПОУ: 41700790\nАдрес: улица Березинская, 52а, Днепр",
    },
    "dest_9": {
        "button": "9. DAF Трак Центр Львов",
        "title": "DAF Трак Центр Львов",
        "details": "DAF Трак Центр Львов\nЕГРПОУ: 31414047\nАдрес: улица Стрийская, 55, с. Солонка",
    },
    "dest_10": {
        "button": "10. Черновцы ДРС-АВТО",
        "title": "Черновцы ДРС-АВТО",
        "details": 'ООО "ДРС-АВТО" / ТОВ "ДРС-АВТО"\nЕГРПОУ: 42941247\nАдрес: улица Энергетическая, 3б, Черновцы',
    },
    "dest_11": {
        "button": "11. Глеваха ЕТС",
        "title": "Глеваха ЕТС",
        "details": "ЕТС Вольво\nЕГРПОУ: 39482580\nАдрес: ул. Сулимы, 9, пгт Глеваха, Киевская область",
    },
}

ORDER_STATUSES = {
    "new": "Новая",
    "assembly": "Сборка на складе",
    "tender": "Запущен тендер",
    "supplier_shipping": "Отправка от поставщика",
    "sent_warehouse": "Отправлено со склада",
    "sent_supplier": "Отправлено поставщиком",
    "cancelled": "Отмена",
}

RETURN_STATUSES = {
    "waiting": "В ожидании",
    "arrived": "Приехала",
    "scrap": "В утиль",
    "used_stock": "На б/у склад",
    "repair": "На восстановление",
    "not_arrived": "Не приехала",
}

MAIN_MENU = ReplyKeyboardMarkup(
    [
        [KeyboardButton("➕ Новая заявка на запчасти")],
        [KeyboardButton("♻️ Снятая запчасть / возврат")],
        [KeyboardButton("🔎 Найти заявку"), KeyboardButton("📋 Мои заявки")],
    ],
    resize_keyboard=True,
)

# =========================
# DATABASE
# =========================

def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def init_db() -> None:
    with get_db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                user_name TEXT,
                state TEXT,
                state_data TEXT,
                updated_at TEXT
            );

            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_number TEXT UNIQUE,
                user_id INTEGER,
                user_name TEXT,
                vehicle_plate TEXT,
                vehicle_model TEXT,
                destination_key TEXT,
                destination_title TEXT,
                destination_details TEXT,
                delivery_details TEXT,
                status TEXT,
                ttn TEXT,
                photo_file_id TEXT,
                group_message_id INTEGER,
                created_at TEXT,
                updated_at TEXT
            );

            CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER,
                part_code TEXT,
                part_name TEXT,
                quantity TEXT
            );

            CREATE TABLE IF NOT EXISTS returns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                return_number TEXT UNIQUE,
                linked_order_id INTEGER,
                user_id INTEGER,
                user_name TEXT,
                vehicle_plate TEXT,
                vehicle_model TEXT,
                delivery_comment TEXT,
                status TEXT,
                photo_file_id TEXT,
                group_message_id INTEGER,
                created_at TEXT,
                updated_at TEXT
            );

            CREATE TABLE IF NOT EXISTS return_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                return_id INTEGER,
                part_code TEXT,
                part_name TEXT,
                quantity TEXT
            );

            CREATE TABLE IF NOT EXISTS actions_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_type TEXT,
                entity_id INTEGER,
                action TEXT,
                old_status TEXT,
                new_status TEXT,
                user_id INTEGER,
                user_name TEXT,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS pending_group_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                chat_id INTEGER,
                action TEXT,
                entity_type TEXT,
                entity_id INTEGER,
                created_at TEXT
            );
            """
        )
        conn.commit()


def user_name_from_update(update: Update) -> str:
    user = update.effective_user
    if not user:
        return "Пользователь"
    if user.username:
        return f"@{user.username}"
    name = " ".join([p for p in [user.first_name, user.last_name] if p])
    return name or str(user.id)


def set_state(user_id: int, state: Optional[str], data: Optional[dict] = None, user_name: str = "") -> None:
    with get_db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO users(user_id,user_name,state,state_data,updated_at) VALUES(?,?,?,?,?)",
            (user_id, user_name, state, json.dumps(data or {}, ensure_ascii=False), now()),
        )
        conn.commit()


def get_state(user_id: int) -> Tuple[Optional[str], dict]:
    with get_db() as conn:
        row = conn.execute("SELECT state,state_data FROM users WHERE user_id=?", (user_id,)).fetchone()
    if not row or not row["state"]:
        return None, {}
    try:
        data = json.loads(row["state_data"] or "{}")
    except json.JSONDecodeError:
        data = {}
    return row["state"], data


def next_number(table: str, prefix: str) -> str:
    with get_db() as conn:
        row = conn.execute(f"SELECT COUNT(*) AS c FROM {table}").fetchone()
    return f"{prefix}{int(row['c']) + 1:06d}"


def log_action(entity_type: str, entity_id: int, action: str, old_status: str, new_status: str, user_id: int, user_name: str) -> None:
    with get_db() as conn:
        conn.execute(
            """INSERT INTO actions_log(entity_type,entity_id,action,old_status,new_status,user_id,user_name,created_at)
               VALUES(?,?,?,?,?,?,?,?)""",
            (entity_type, entity_id, action, old_status, new_status, user_id, user_name, now()),
        )
        conn.commit()

# =========================
# PARSING
# =========================

def parse_order_text(text: str) -> Tuple[str, str, List[dict]]:
    clean = (text or "").strip()
    lines = [line.strip() for line in clean.splitlines() if line.strip()]
    if len(lines) < 2:
        raise ValueError("Нужно указать авто и хотя бы одну запчасть.")

    first = lines[0]
    first_parts = first.split()
    vehicle_plate = first_parts[0].upper() if first_parts else ""
    vehicle_model = " ".join(first_parts[1:]).strip()

    items: List[dict] = []
    for line in lines[1:]:
        normalized = line.replace("—", "-").replace("–", "-")
        chunks = [chunk.strip() for chunk in normalized.split("-") if chunk.strip()]
        if len(chunks) >= 3:
            part_code = chunks[0]
            quantity = chunks[1].replace("шт", "").replace(".", "").strip()
            part_name = " - ".join(chunks[2:]).strip()
        elif len(chunks) == 2:
            part_code = chunks[0]
            quantity = "1"
            part_name = chunks[1]
        else:
            # fallback: code + name by spaces
            tokens = line.split(maxsplit=1)
            part_code = tokens[0] if tokens else ""
            quantity = "1"
            part_name = tokens[1] if len(tokens) > 1 else line
        if part_code and part_name:
            items.append({"part_code": part_code, "quantity": quantity or "1", "part_name": part_name})

    if not vehicle_plate or not items:
        raise ValueError("Не удалось распознать заявку. Проверьте формат.")
    return vehicle_plate, vehicle_model, items


def parse_return_text(text: str) -> Tuple[str, str, str, str]:
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    if len(lines) < 3:
        raise ValueError("Нужно минимум 3 строки: госномер, код, наименование.")
    vehicle_plate = lines[0].upper()
    part_code = lines[1]
    part_name = lines[2]
    delivery_comment = "\n".join(lines[3:]).strip() or "Привезет водитель"
    return vehicle_plate, part_code, part_name, delivery_comment


def parse_specific_return_lines(text: str) -> List[dict]:
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    items: List[dict] = []
    for line in lines:
        normalized = line.replace("—", "-").replace("–", "-")
        chunks = [chunk.strip() for chunk in normalized.split("-") if chunk.strip()]
        if len(chunks) >= 2:
            items.append({
                "part_code": chunks[0],
                "part_name": chunks[1],
                "quantity": "1",
                "delivery_comment": " - ".join(chunks[2:]).strip() or "Привезет водитель",
            })
    if not items:
        raise ValueError("Не удалось распознать запчасть. Пример: 789456 — Стартер — привезет водитель")
    return items

# =========================
# KEYBOARDS
# =========================

def destinations_keyboard() -> InlineKeyboardMarkup:
    rows = []
    keys = list(DESTINATIONS.keys())
    for i in range(0, len(keys), 2):
        row = []
        for key in keys[i:i+2]:
            row.append(InlineKeyboardButton(DESTINATIONS[key]["button"], callback_data=f"dest:{key}"))
        rows.append(row)
    rows.append([InlineKeyboardButton("12. Другое", callback_data="dest:other")])
    return InlineKeyboardMarkup(rows)


def order_keyboard(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔵 Сборка на складе", callback_data=f"order_status:{order_id}:assembly")],
        [InlineKeyboardButton("🟣 Запущен тендер", callback_data=f"order_status:{order_id}:tender")],
        [InlineKeyboardButton("🟠 Отправка от поставщика", callback_data=f"order_status:{order_id}:supplier_shipping")],
        [InlineKeyboardButton("📦 Внести ТТН", callback_data=f"order_ttn:{order_id}")],
        [InlineKeyboardButton("❌ Отмена", callback_data=f"order_status:{order_id}:cancelled")],
    ])


def return_question_keyboard(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("♻️ Да, на все запчасти", callback_data=f"return_all:{order_id}")],
        [InlineKeyboardButton("✍️ Выбрать конкретную запчасть", callback_data=f"return_specific:{order_id}")],
        [InlineKeyboardButton("➡️ Нет", callback_data=f"return_none:{order_id}")],
    ])


def return_keyboard(return_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Приехала", callback_data=f"return_status:{return_id}:arrived")],
        [InlineKeyboardButton("🗑 В утиль", callback_data=f"return_status:{return_id}:scrap")],
        [InlineKeyboardButton("📦 На б/у склад", callback_data=f"return_status:{return_id}:used_stock")],
        [InlineKeyboardButton("🔧 На восстановление", callback_data=f"return_status:{return_id}:repair")],
        [InlineKeyboardButton("❌ Не приехала", callback_data=f"return_status:{return_id}:not_arrived")],
    ])

# =========================
# DATA HELPERS
# =========================

def create_order(user_id: int, user_name: str, plate: str, model: str, items: List[dict], dest_key: str, dest_title: str, dest_details: str, delivery_details: str, photo_file_id: Optional[str]) -> int:
    order_number = next_number("orders", "")
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO orders(order_number,user_id,user_name,vehicle_plate,vehicle_model,destination_key,destination_title,destination_details,delivery_details,status,ttn,photo_file_id,created_at,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (order_number, user_id, user_name, plate, model, dest_key, dest_title, dest_details, delivery_details, ORDER_STATUSES["new"], None, photo_file_id, now(), now()),
        )
        order_id = cur.lastrowid
        for item in items:
            cur.execute(
                "INSERT INTO order_items(order_id,part_code,part_name,quantity) VALUES(?,?,?,?)",
                (order_id, item["part_code"], item["part_name"], item.get("quantity", "1")),
            )
        conn.commit()
    log_action("order", order_id, "Создана заявка", "", ORDER_STATUSES["new"], user_id, user_name)
    return order_id


def get_order(order_id: int) -> sqlite3.Row:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    if not row:
        raise ValueError("Order not found")
    return row


def get_order_items(order_id: int) -> List[sqlite3.Row]:
    with get_db() as conn:
        return conn.execute("SELECT * FROM order_items WHERE order_id=? ORDER BY id", (order_id,)).fetchall()


def create_return(user_id: int, user_name: str, plate: str, model: str, items: List[dict], delivery_comment: str, photo_file_id: Optional[str], linked_order_id: Optional[int] = None) -> int:
    return_number = next_number("returns", "BU-")
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO returns(return_number,linked_order_id,user_id,user_name,vehicle_plate,vehicle_model,delivery_comment,status,photo_file_id,created_at,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (return_number, linked_order_id, user_id, user_name, plate, model, delivery_comment, RETURN_STATUSES["waiting"], photo_file_id, now(), now()),
        )
        return_id = cur.lastrowid
        for item in items:
            cur.execute(
                "INSERT INTO return_items(return_id,part_code,part_name,quantity) VALUES(?,?,?,?)",
                (return_id, item["part_code"], item["part_name"], item.get("quantity", "1")),
            )
        conn.commit()
    log_action("return", return_id, "Создан возврат", "", RETURN_STATUSES["waiting"], user_id, user_name)
    return return_id


def get_return(return_id: int) -> sqlite3.Row:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM returns WHERE id=?", (return_id,)).fetchone()
    if not row:
        raise ValueError("Return not found")
    return row


def get_return_items(return_id: int) -> List[sqlite3.Row]:
    with get_db() as conn:
        return conn.execute("SELECT * FROM return_items WHERE return_id=? ORDER BY id", (return_id,)).fetchall()

# =========================
# FORMATTERS
# =========================

def fmt_items(items: List[sqlite3.Row]) -> str:
    lines = []
    for idx, item in enumerate(items, 1):
        qty = item["quantity"] or "1"
        lines.append(f"{idx}. {item['part_code']} — {qty} шт — {item['part_name']}")
    return "\n".join(lines)


def fmt_return_items(items: List[sqlite3.Row]) -> str:
    lines = []
    for idx, item in enumerate(items, 1):
        qty = item["quantity"] or "1"
        qty_text = f" — {qty} шт" if qty and qty != "1" else ""
        lines.append(f"{idx}. {item['part_code']} — {item['part_name']}{qty_text}")
    return "\n".join(lines)


def order_card(order_id: int) -> str:
    order = get_order(order_id)
    items = get_order_items(order_id)
    return (
        f"🆕 Заявка №{order['order_number']}\n"
        f"📦 Новая заявка на отправку запчастей\n\n"
        f"🚛 Авто: {order['vehicle_plate']}\n"
        f"🚘 Модель: {order['vehicle_model'] or '—'}\n\n"
        f"📋 Запчасти:\n{fmt_items(items)}\n\n"
        f"📍 Контрагент: {order['destination_title']}\n\n"
        f"🏢 Данные контрагента:\n{order['destination_details'] or '—'}\n\n"
        f"🚚 Контакты и условия доставки:\n{order['delivery_details'] or '—'}\n\n"
        f"👤 Заказчик: {order['user_name']}\n"
        f"📅 Дата: {order['created_at']}\n\n"
        f"🟡 Статус: {order['status']}"
        + (f"\n📦 ТТН НП: {order['ttn']}" if order['ttn'] else "")
    )


def return_card(return_id: int) -> str:
    ret = get_return(return_id)
    items = get_return_items(return_id)
    linked = ""
    if ret["linked_order_id"]:
        try:
            linked_order = get_order(ret["linked_order_id"])
            linked = f"Связан с заявкой №{linked_order['order_number']}\n\n"
        except Exception:
            linked = f"Связан с заявкой ID {ret['linked_order_id']}\n\n"
    return (
        f"♻️ Возврат №{ret['return_number']}\n"
        f"{linked}"
        f"🚛 Авто: {ret['vehicle_plate']}\n"
        f"🚘 Модель: {ret['vehicle_model'] or '—'}\n\n"
        f"📦 Ожидаемые снятые запчасти:\n{fmt_return_items(items)}\n\n"
        f"🚚 Доставка: {ret['delivery_comment'] or 'Привезет водитель'}\n\n"
        f"👤 Уведомил: {ret['user_name']}\n"
        f"📅 Дата: {ret['created_at']}\n\n"
        f"🟡 Статус: {ret['status']}"
    )


def short_order_notification(order_id: int) -> str:
    order = get_order(order_id)
    return f"🔔 Обновление по заявке №{order['order_number']}\n\n🚛 Авто: {order['vehicle_plate']}\n📦 Статус: {order['status']}"


def full_ttn_notification(order_id: int) -> str:
    order = get_order(order_id)
    items = get_order_items(order_id)
    return (
        f"✅ Заявка №{order['order_number']} отправлена\n\n"
        f"🚛 Авто: {order['vehicle_plate']} / {order['vehicle_model'] or '—'}\n\n"
        f"📦 Запчасти:\n{fmt_items(items)}\n\n"
        f"📍 Контрагент: {order['destination_title']}\n\n"
        f"🚚 Контакты и условия доставки:\n{order['delivery_details'] or '—'}\n\n"
        f"🚚 Служба доставки: Новая Почта\n"
        f"📦 ТТН: {order['ttn']}\n\n"
        f"Статус: {order['status']}"
    )


def return_notification(return_id: int) -> str:
    ret = get_return(return_id)
    items = get_return_items(return_id)
    first = items[0] if items else None
    part = first["part_name"] if first else "—"
    return f"🔔 Обновление по возврату №{ret['return_number']}\n\n🚛 Авто: {ret['vehicle_plate']}\n📦 Запчасть: {part}\nСтатус: {ret['status']}"

# =========================
# TELEGRAM HANDLERS
# =========================

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    set_state(update.effective_user.id, None, user_name=user_name_from_update(update))
    await update.message.reply_text(
        "Бот заявок на запчасти и возвраты б/у запчастей.\nВыберите действие:",
        reply_markup=MAIN_MENU,
    )


async def text_or_photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_user:
        return

    chat = update.effective_chat
    user_id = update.effective_user.id
    user_name = user_name_from_update(update)
    text = update.message.text or update.message.caption or ""
    photo_file_id = update.message.photo[-1].file_id if update.message.photo else None

    # Pending TTN from group
    if chat and chat.type in ("group", "supergroup"):
        await handle_group_text(update, context, text)
        return

    # Main menu actions
    if text == "➕ Новая заявка на запчасти":
        set_state(user_id, "waiting_order", {}, user_name)
        await update.message.reply_text(
            "Отправьте заявку одним сообщением или фото с подписью.\n\n"
            "Формат:\n"
            "АА1234ВС DAF XF\n\n"
            "123456 — 2 шт — Стартер\n"
            "789456 — 1 шт — Генератор",
            reply_markup=MAIN_MENU,
        )
        return

    if text == "♻️ Снятая запчасть / возврат":
        set_state(user_id, "waiting_return", {}, user_name)
        await update.message.reply_text(
            "Отправьте данные возврата одним сообщением или фото с подписью.\n\n"
            "Формат:\n"
            "АА1234ВС\n"
            "123456\n"
            "Стартер\n"
            "Привезет водитель",
            reply_markup=MAIN_MENU,
        )
        return

    if text == "🔎 Найти заявку":
        set_state(user_id, "waiting_search", {}, user_name)
        await update.message.reply_text("Введите госномер, код запчасти, номер заявки, наименование или ТТН:", reply_markup=MAIN_MENU)
        return

    if text == "📋 Мои заявки":
        await show_my_requests(update, context)
        return

    state, data = get_state(user_id)

    if state == "waiting_order":
        try:
            plate, model, items = parse_order_text(text)
        except ValueError as e:
            await update.message.reply_text(f"❌ {e}\n\nПопробуйте еще раз.", reply_markup=MAIN_MENU)
            return
        set_state(user_id, "waiting_destination", {
            "plate": plate,
            "model": model,
            "items": items,
            "photo_file_id": photo_file_id,
        }, user_name)
        await update.message.reply_text("Выберите контрагента:", reply_markup=destinations_keyboard())
        return

    if state == "waiting_delivery_details":
        data["delivery_details"] = text.strip()
        order_id = create_order_from_state(user_id, user_name, data)
        set_state(user_id, None, user_name=user_name)
        await send_order_to_group(context, order_id)
        await update.message.reply_text(
            f"✅ Заявка №{get_order(order_id)['order_number']} создана и отправлена на склад.\n\n"
            "По этой заявке ожидается возврат снятых б/у запчастей?",
            reply_markup=return_question_keyboard(order_id),
        )
        return

    if state == "waiting_other_destination_details":
        data["destination_key"] = "other"
        data["destination_title"] = "Другое"
        data["destination_details"] = text.strip()
        data["delivery_details"] = text.strip()
        order_id = create_order_from_state(user_id, user_name, data)
        set_state(user_id, None, user_name=user_name)
        await send_order_to_group(context, order_id)
        await update.message.reply_text(
            f"✅ Заявка №{get_order(order_id)['order_number']} создана и отправлена на склад.\n\n"
            "По этой заявке ожидается возврат снятых б/у запчастей?",
            reply_markup=return_question_keyboard(order_id),
        )
        return

    if state == "waiting_return":
        try:
            plate, part_code, part_name, delivery_comment = parse_return_text(text)
        except ValueError as e:
            await update.message.reply_text(f"❌ {e}\n\nПопробуйте еще раз.", reply_markup=MAIN_MENU)
            return
        return_id = create_return(
            user_id=user_id,
            user_name=user_name,
            plate=plate,
            model="",
            items=[{"part_code": part_code, "part_name": part_name, "quantity": "1"}],
            delivery_comment=delivery_comment,
            photo_file_id=photo_file_id,
            linked_order_id=None,
        )
        set_state(user_id, None, user_name=user_name)
        await send_return_to_group(context, return_id)
        await update.message.reply_text(f"✅ Возврат №{get_return(return_id)['return_number']} отправлен в группу б/у.", reply_markup=MAIN_MENU)
        return

    if state == "waiting_specific_return":
        order_id = int(data["order_id"])
        order = get_order(order_id)
        try:
            items = parse_specific_return_lines(text)
        except ValueError as e:
            await update.message.reply_text(f"❌ {e}\n\nПопробуйте еще раз.", reply_markup=MAIN_MENU)
            return
        # Берем доставку из первой строки, если указана после второго тире
        delivery_comment = items[0].get("delivery_comment") or "Привезет водитель"
        return_id = create_return(
            user_id=user_id,
            user_name=user_name,
            plate=order["vehicle_plate"],
            model=order["vehicle_model"],
            items=items,
            delivery_comment=delivery_comment,
            photo_file_id=photo_file_id,
            linked_order_id=order_id,
        )
        set_state(user_id, None, user_name=user_name)
        await send_return_to_group(context, return_id)
        await update.message.reply_text(f"✅ Возврат №{get_return(return_id)['return_number']} создан и отправлен в группу б/у.", reply_markup=MAIN_MENU)
        return

    if state == "waiting_search":
        set_state(user_id, None, user_name=user_name)
        await search_and_reply(update, context, text.strip())
        return

    await update.message.reply_text("Выберите действие в меню.", reply_markup=MAIN_MENU)


def create_order_from_state(user_id: int, user_name: str, data: dict) -> int:
    return create_order(
        user_id=user_id,
        user_name=user_name,
        plate=data["plate"],
        model=data.get("model", ""),
        items=data["items"],
        dest_key=data.get("destination_key", ""),
        dest_title=data.get("destination_title", ""),
        dest_details=data.get("destination_details", ""),
        delivery_details=data.get("delivery_details", ""),
        photo_file_id=data.get("photo_file_id"),
    )


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not update.effective_user:
        return
    await query.answer()
    data = query.data or ""
    user_id = update.effective_user.id
    user_name = user_name_from_update(update)

    if data.startswith("dest:"):
        dest_key = data.split(":", 1)[1]
        state, state_data = get_state(user_id)
        if state != "waiting_destination":
            await query.message.reply_text("Заявка не найдена в текущем состоянии. Начните заново.", reply_markup=MAIN_MENU)
            return
        if dest_key == "other":
            set_state(user_id, "waiting_other_destination_details", state_data, user_name)
            await query.message.reply_text(
                "Введите все данные по получателю и доставке одним сообщением:\n\n"
                "Контрагент / получатель:\n"
                "Город:\n"
                "Адрес:\n"
                "Контакт:\n"
                "Телефон:\n"
                "Условия доставки:\n"
                "Комментарий:",
                reply_markup=MAIN_MENU,
            )
            return
        dest = DESTINATIONS[dest_key]
        state_data.update({
            "destination_key": dest_key,
            "destination_title": dest["title"],
            "destination_details": dest["details"],
        })
        set_state(user_id, "waiting_delivery_details", state_data, user_name)
        await query.message.reply_text(
            f"Вы выбрали:\n\n{dest['button']}\n\n{dest['details']}\n\n"
            "Введите актуальные контакты и условия доставки одним сообщением.\n\n"
            "Например:\n"
            "Контакт: Сергей\n"
            "Телефон: +380...\n"
            "Доставка: НП / адресная доставка НП / такси / доставка поставщика / самовывоз\n"
            "Комментарий: отправить сегодня, срочно и т.д.",
            reply_markup=MAIN_MENU,
        )
        return

    if data.startswith("order_status:"):
        _, order_id_s, status_key = data.split(":")
        await update_order_status(context, int(order_id_s), status_key, user_id, user_name)
        await query.edit_message_text(order_card(int(order_id_s)), reply_markup=order_keyboard(int(order_id_s)))
        return

    if data.startswith("order_ttn:"):
        order_id = int(data.split(":")[1])
        with get_db() as conn:
            conn.execute(
                "INSERT INTO pending_group_actions(user_id,chat_id,action,entity_type,entity_id,created_at) VALUES(?,?,?,?,?,?)",
                (user_id, query.message.chat_id, "awaiting_ttn", "order", order_id, now()),
            )
            conn.commit()
        await query.message.reply_text(f"Введите номер ТТН Новой Почты для заявки №{get_order(order_id)['order_number']}:")
        return

    if data.startswith("return_all:"):
        order_id = int(data.split(":")[1])
        order = get_order(order_id)
        order_items = get_order_items(order_id)
        items = [{"part_code": i["part_code"], "part_name": i["part_name"], "quantity": i["quantity"]} for i in order_items]
        return_id = create_return(
            user_id=user_id,
            user_name=user_name,
            plate=order["vehicle_plate"],
            model=order["vehicle_model"],
            items=items,
            delivery_comment="Привезет водитель",
            photo_file_id=None,
            linked_order_id=order_id,
        )
        await send_return_to_group(context, return_id)
        await query.message.reply_text(f"✅ Возврат №{get_return(return_id)['return_number']} создан на все запчасти.", reply_markup=MAIN_MENU)
        return

    if data.startswith("return_specific:"):
        order_id = int(data.split(":")[1])
        set_state(user_id, "waiting_specific_return", {"order_id": order_id}, user_name)
        await query.message.reply_text(
            "Напишите, какую снятую запчасть ожидаем обратно.\n\n"
            "Можно указать одну или несколько позиций.\n\n"
            "Формат:\n"
            "код — наименование — кто привезет\n\n"
            "Пример:\n"
            "789456 — Стартер — привезет водитель",
            reply_markup=MAIN_MENU,
        )
        return

    if data.startswith("return_none:"):
        order_id = int(data.split(":")[1])
        await query.message.reply_text(f"Готово. Заявка №{get_order(order_id)['order_number']} создана без возврата б/у.", reply_markup=MAIN_MENU)
        return

    if data.startswith("return_status:"):
        _, return_id_s, status_key = data.split(":")
        await update_return_status(context, int(return_id_s), status_key, user_id, user_name)
        await query.edit_message_text(return_card(int(return_id_s)), reply_markup=return_keyboard(int(return_id_s)))
        return


async def handle_group_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    if not update.effective_user or not update.effective_chat or not text:
        return
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    user_name = user_name_from_update(update)
    with get_db() as conn:
        pending = conn.execute(
            "SELECT * FROM pending_group_actions WHERE user_id=? AND chat_id=? ORDER BY id DESC LIMIT 1",
            (user_id, chat_id),
        ).fetchone()
    if not pending:
        return

    if pending["action"] == "awaiting_ttn" and pending["entity_type"] == "order":
        order_id = int(pending["entity_id"])
        ttn = text.strip()
        order = get_order(order_id)
        old_status = order["status"]
        new_status = ORDER_STATUSES["sent_supplier"] if old_status == ORDER_STATUSES["supplier_shipping"] else ORDER_STATUSES["sent_warehouse"]
        with get_db() as conn:
            conn.execute("UPDATE orders SET ttn=?, status=?, updated_at=? WHERE id=?", (ttn, new_status, now(), order_id))
            conn.execute("DELETE FROM pending_group_actions WHERE id=?", (pending["id"],))
            conn.commit()
        log_action("order", order_id, f"Внесена ТТН {ttn}", old_status, new_status, user_id, user_name)
        updated_order = get_order(order_id)
        try:
            await context.bot.edit_message_text(
                chat_id=PARTS_GROUP_ID,
                message_id=updated_order["group_message_id"],
                text=order_card(order_id),
                reply_markup=order_keyboard(order_id),
            )
        except Exception:
            pass
        try:
            await context.bot.send_message(chat_id=updated_order["user_id"], text=full_ttn_notification(order_id))
        except Exception:
            pass
        await update.message.reply_text(f"✅ ТТН сохранена. Статус: {new_status}")


async def update_order_status(context: ContextTypes.DEFAULT_TYPE, order_id: int, status_key: str, user_id: int, user_name: str) -> None:
    if status_key not in ORDER_STATUSES:
        return
    order = get_order(order_id)
    old_status = order["status"]
    new_status = ORDER_STATUSES[status_key]
    with get_db() as conn:
        conn.execute("UPDATE orders SET status=?, updated_at=? WHERE id=?", (new_status, now(), order_id))
        conn.commit()
    log_action("order", order_id, "Изменен статус", old_status, new_status, user_id, user_name)
    try:
        await context.bot.send_message(chat_id=order["user_id"], text=short_order_notification(order_id))
    except Exception:
        pass


async def update_return_status(context: ContextTypes.DEFAULT_TYPE, return_id: int, status_key: str, user_id: int, user_name: str) -> None:
    if status_key not in RETURN_STATUSES:
        return
    ret = get_return(return_id)
    old_status = ret["status"]
    new_status = RETURN_STATUSES[status_key]
    with get_db() as conn:
        conn.execute("UPDATE returns SET status=?, updated_at=? WHERE id=?", (new_status, now(), return_id))
        conn.commit()
    log_action("return", return_id, "Изменен статус", old_status, new_status, user_id, user_name)
    try:
        await context.bot.send_message(chat_id=ret["user_id"], text=return_notification(return_id))
    except Exception:
        pass


async def send_order_to_group(context: ContextTypes.DEFAULT_TYPE, order_id: int) -> None:
    order = get_order(order_id)
    msg = await context.bot.send_message(PARTS_GROUP_ID, order_card(order_id), reply_markup=order_keyboard(order_id))
    with get_db() as conn:
        conn.execute("UPDATE orders SET group_message_id=? WHERE id=?", (msg.message_id, order_id))
        conn.commit()
    if order["photo_file_id"]:
        await context.bot.send_photo(PARTS_GROUP_ID, order["photo_file_id"], caption=f"Фото к заявке №{order['order_number']}")


async def send_return_to_group(context: ContextTypes.DEFAULT_TYPE, return_id: int) -> None:
    ret = get_return(return_id)
    msg = await context.bot.send_message(RETURNS_GROUP_ID, return_card(return_id), reply_markup=return_keyboard(return_id))
    with get_db() as conn:
        conn.execute("UPDATE returns SET group_message_id=? WHERE id=?", (msg.message_id, return_id))
        conn.commit()
    if ret["photo_file_id"]:
        await context.bot.send_photo(RETURNS_GROUP_ID, ret["photo_file_id"], caption=f"Фото к возврату №{ret['return_number']}")


async def search_and_reply(update: Update, context: ContextTypes.DEFAULT_TYPE, q: str) -> None:
    pattern = f"%{q}%"
    with get_db() as conn:
        orders = conn.execute(
            """
            SELECT DISTINCT o.* FROM orders o
            LEFT JOIN order_items i ON i.order_id=o.id
            WHERE o.order_number LIKE ? OR o.vehicle_plate LIKE ? OR o.vehicle_model LIKE ?
               OR o.ttn LIKE ? OR i.part_code LIKE ? OR i.part_name LIKE ?
            ORDER BY o.id DESC LIMIT 10
            """,
            (pattern, pattern, pattern, pattern, pattern, pattern),
        ).fetchall()
        returns = conn.execute(
            """
            SELECT DISTINCT r.* FROM returns r
            LEFT JOIN return_items i ON i.return_id=r.id
            WHERE r.return_number LIKE ? OR r.vehicle_plate LIKE ? OR r.vehicle_model LIKE ?
               OR i.part_code LIKE ? OR i.part_name LIKE ?
            ORDER BY r.id DESC LIMIT 10
            """,
            (pattern, pattern, pattern, pattern, pattern),
        ).fetchall()
    if not orders and not returns:
        await update.message.reply_text("Ничего не найдено.", reply_markup=MAIN_MENU)
        return
    parts = []
    if orders:
        parts.append("📦 Заявки на запчасти:")
        for o in orders:
            parts.append(f"№{o['order_number']} | {o['vehicle_plate']} | {o['status']} | ТТН: {o['ttn'] or '—'}")
    if returns:
        parts.append("\n♻️ Возвраты б/у:")
        for r in returns:
            parts.append(f"{r['return_number']} | {r['vehicle_plate']} | {r['status']}")
    await update.message.reply_text("\n".join(parts), reply_markup=MAIN_MENU)


async def show_my_requests(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    with get_db() as conn:
        orders = conn.execute("SELECT * FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 5", (user_id,)).fetchall()
        returns = conn.execute("SELECT * FROM returns WHERE user_id=? ORDER BY id DESC LIMIT 5", (user_id,)).fetchall()
    if not orders and not returns:
        await update.message.reply_text("У вас пока нет заявок.", reply_markup=MAIN_MENU)
        return
    lines = []
    if orders:
        lines.append("📦 Последние заявки:")
        for o in orders:
            lines.append(f"№{o['order_number']} | {o['vehicle_plate']} | {o['status']}")
    if returns:
        lines.append("\n♻️ Последние возвраты:")
        for r in returns:
            lines.append(f"{r['return_number']} | {r['vehicle_plate']} | {r['status']}")
    await update.message.reply_text("\n".join(lines), reply_markup=MAIN_MENU)

# =========================
# WEB PAGE
# =========================

def esc(value: Any) -> str:
    return html.escape(str(value or ""))


def web_page(q: str = "", status: str = "") -> str:
    q_like = f"%{q}%"
    with get_db() as conn:
        if q:
            orders = conn.execute(
                """
                SELECT DISTINCT o.* FROM orders o LEFT JOIN order_items i ON i.order_id=o.id
                WHERE o.order_number LIKE ? OR o.vehicle_plate LIKE ? OR o.vehicle_model LIKE ? OR o.ttn LIKE ?
                   OR o.destination_title LIKE ? OR i.part_code LIKE ? OR i.part_name LIKE ?
                ORDER BY o.id DESC LIMIT 300
                """,
                (q_like, q_like, q_like, q_like, q_like, q_like, q_like),
            ).fetchall()
            returns = conn.execute(
                """
                SELECT DISTINCT r.* FROM returns r LEFT JOIN return_items i ON i.return_id=r.id
                WHERE r.return_number LIKE ? OR r.vehicle_plate LIKE ? OR r.vehicle_model LIKE ? OR i.part_code LIKE ? OR i.part_name LIKE ?
                ORDER BY r.id DESC LIMIT 300
                """,
                (q_like, q_like, q_like, q_like, q_like),
            ).fetchall()
        else:
            orders = conn.execute("SELECT * FROM orders ORDER BY id DESC LIMIT 300").fetchall()
            returns = conn.execute("SELECT * FROM returns ORDER BY id DESC LIMIT 300").fetchall()

    order_rows = []
    for o in orders:
        items = get_order_items(o["id"])
        order_rows.append(f"""
        <tr>
          <td>{esc(o['created_at'])}</td><td>№{esc(o['order_number'])}</td><td>{esc(o['vehicle_plate'])}</td><td>{esc(o['vehicle_model'])}</td>
          <td>{esc(fmt_items(items))}</td><td>{esc(o['destination_title'])}</td><td>{esc(o['delivery_details'])}</td>
          <td>{esc(o['status'])}</td><td>{esc(o['ttn'])}</td>
        </tr>
        """)
    return_rows = []
    for r in returns:
        items = get_return_items(r["id"])
        linked = ""
        if r["linked_order_id"]:
            try:
                linked = "№" + get_order(r["linked_order_id"])["order_number"]
            except Exception:
                linked = str(r["linked_order_id"])
        return_rows.append(f"""
        <tr>
          <td>{esc(r['created_at'])}</td><td>{esc(r['return_number'])}</td><td>{esc(r['vehicle_plate'])}</td>
          <td>{esc(fmt_return_items(items))}</td><td>{esc(r['delivery_comment'])}</td><td>{esc(r['status'])}</td><td>{esc(linked)}</td>
        </tr>
        """)

    return f"""
    <!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <title>Заявки ТКГ</title>
    <style>
      body {{ font-family: Arial, sans-serif; margin: 20px; background: #f6f7f9; color: #222; }}
      h1 {{ margin-bottom: 8px; }} h2 {{ margin-top: 30px; }}
      form {{ background: white; padding: 14px; border-radius: 12px; box-shadow: 0 1px 4px #ddd; margin-bottom: 20px; }}
      input {{ padding: 10px; min-width: 280px; border: 1px solid #ccc; border-radius: 8px; }}
      button {{ padding: 10px 14px; border: 0; background: #1f6feb; color: white; border-radius: 8px; cursor: pointer; }}
      table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 1px 4px #ddd; }}
      th, td {{ border-bottom: 1px solid #eee; padding: 9px; vertical-align: top; text-align: left; white-space: pre-wrap; }}
      th {{ background: #23395d; color: white; }}
      tr:hover td {{ background: #f1f5ff; }}
    </style></head><body>
    <h1>Заявки ТКГ</h1>
    <form method="get">
      <input name="q" value="{esc(q)}" placeholder="Поиск: госномер, код, ТТН, заявка, название">
      <button type="submit">Найти</button>
      <a href="/" style="margin-left:10px;">Сбросить</a>
    </form>

    <h2>📦 Заявки на новые запчасти</h2>
    <table><thead><tr><th>Дата</th><th>№</th><th>Госномер</th><th>Модель</th><th>Запчасти</th><th>Контрагент</th><th>Доставка/контакты</th><th>Статус</th><th>ТТН</th></tr></thead>
    <tbody>{''.join(order_rows) or '<tr><td colspan="9">Нет данных</td></tr>'}</tbody></table>

    <h2>♻️ Возвраты б/у запчастей</h2>
    <table><thead><tr><th>Дата</th><th>№</th><th>Госномер</th><th>Запчасти</th><th>Доставка</th><th>Статус</th><th>Связь</th></tr></thead>
    <tbody>{''.join(return_rows) or '<tr><td colspan="7">Нет данных</td></tr>'}</tbody></table>
    </body></html>
    """

# =========================
# FASTAPI + PTB WEBHOOK
# =========================

telegram_app = Application.builder().token(BOT_TOKEN).build()
telegram_app.add_handler(CommandHandler("start", cmd_start))
telegram_app.add_handler(CallbackQueryHandler(callback_handler))
telegram_app.add_handler(MessageHandler((filters.TEXT | filters.PHOTO) & ~filters.COMMAND, text_or_photo_handler))

app = FastAPI()

@app.on_event("startup")
async def on_startup() -> None:
    init_db()
    await telegram_app.initialize()
    await telegram_app.start()
    await telegram_app.bot.set_webhook(f"{WEBHOOK_URL}/webhook")

@app.on_event("shutdown")
async def on_shutdown() -> None:
    await telegram_app.bot.delete_webhook()
    await telegram_app.stop()
    await telegram_app.shutdown()

@app.post("/webhook")
async def webhook(request: Request) -> PlainTextResponse:
    data = await request.json()
    update = Update.de_json(data, telegram_app.bot)
    await telegram_app.process_update(update)
    return PlainTextResponse("ok")

@app.get("/", response_class=HTMLResponse)
async def index(q: str = "") -> HTMLResponse:
    init_db()
    return HTMLResponse(web_page(q=q))

@app.get("/health")
async def health() -> PlainTextResponse:
    return PlainTextResponse("ok")
