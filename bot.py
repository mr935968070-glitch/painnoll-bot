import os
import logging
import sqlite3
from datetime import datetime, timedelta
import telebot
import time
from telebot import types
from apscheduler.schedulers.background import BackgroundScheduler

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN env kerak. Iltimos muhitda sozlang.")
ADMIN_IDS = [851458432]
DB_PATH = "painnoll_bot.db"
TIMEZONE_OFFSET = 0

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot.log", encoding="utf-8"),
    ],
)
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
scheduler = BackgroundScheduler()

main_kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
main_kb.add(types.KeyboardButton("📝 Mening profilim"), types.KeyboardButton("🍽 Ovqatlanish"))
main_kb.add(types.KeyboardButton("💊 Mahsulotlar"), types.KeyboardButton("📊 Natijam"))
main_kb.add(types.KeyboardButton("📞 Bog'lanish"), types.KeyboardButton("🎁 Aksiya"))
main_kb.add(types.KeyboardButton("🩺 Registratsiya"))

product_kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
product_kb.add(types.KeyboardButton("🌿 Painnoll"))
product_kb.add(types.KeyboardButton("🍃 BioDetox"))
product_kb.add(types.KeyboardButton("💪 VitaPro"))
product_kb.add(types.KeyboardButton("🔬 NutraMax"))
product_kb.add(types.KeyboardButton("⬅️ Orqaga"))

issue_kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
issue_kb.add(types.KeyboardButton("🦵 Suyak va bo'g'imlar"))
issue_kb.add(types.KeyboardButton("🍽 Oshqozon / hazm"))
issue_kb.add(types.KeyboardButton("🧔 Prostata"))
issue_kb.add(types.KeyboardButton("🍋 Detoks / vazn"))
issue_kb.add(types.KeyboardButton("⬅️ Orqaga"))

daily_inline = types.InlineKeyboardMarkup()
daily_inline.add(
    types.InlineKeyboardButton("✅ Amal bajarildi", callback_data="done"),
    types.InlineKeyboardButton("⏰ Keyinroq eslat", callback_data="remind_later"),
)

def db_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    conn = db_conn()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            chat_id INTEGER PRIMARY KEY,
            name TEXT,
            age INTEGER,
            weight REAL,
            height REAL,
            product TEXT,
            issue TEXT,
            start_date TEXT,
            week INTEGER DEFAULT 1,
            created_at TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            date TEXT,
            reminder_time TEXT,
            done INTEGER DEFAULT 0
        )
        """
    )
    conn.commit()
    try:
        cur.execute("ALTER TABLE users ADD COLUMN consult_mode INTEGER DEFAULT 0")
        conn.commit()
    except Exception:
        pass
    conn.close()

def get_user(chat_id: int):
    conn = db_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE chat_id = ?", (chat_id,))
    row = cur.fetchone()
    conn.close()
    return row

def add_user(chat_id: int, name: str, age=None, weight=None, height=None, product=None, issue=None):
    now = datetime.utcnow().isoformat()
    conn = db_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT OR REPLACE INTO users (chat_id, name, age, weight, height, product, issue, start_date, week, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (chat_id, name, age, weight, height, product, issue, now, 1, now),
    )
    conn.commit()
    conn.close()

def update_user_field(chat_id: int, field: str, value):
    conn = db_conn()
    cur = conn.cursor()
    cur.execute(f"UPDATE users SET {field} = ? WHERE chat_id = ?", (value, chat_id))
    conn.commit()
    conn.close()

def log_progress(chat_id: int, reminder_time: str, done: bool):
    d = datetime.utcnow().date().isoformat()
    conn = db_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO progress (chat_id, date, reminder_time, done) VALUES (?, ?, ?, ?)",
        (chat_id, d, reminder_time, 1 if done else 0),
    )
    conn.commit()
    conn.close()

def list_user_ids():
    conn = db_conn()
    cur = conn.cursor()
    cur.execute("SELECT chat_id FROM users")
    rows = cur.fetchall()
    conn.close()
    return [r[0] for r in rows]

admin_kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
admin_kb.add(types.KeyboardButton("👥 Foydalanuvchilar"), types.KeyboardButton("📈 Statistika"))
admin_kb.add(types.KeyboardButton("📣 Anons yuborish"))
admin_kb.add(types.KeyboardButton("⬅️ Orqaga"))

admin_modes = {}

def set_consult_mode(chat_id: int, on: bool):
    conn = db_conn()
    cur = conn.cursor()
    cur.execute("UPDATE users SET consult_mode = ? WHERE chat_id = ?", (1 if on else 0, chat_id))
    conn.commit()
    conn.close()

def get_consult_mode(chat_id: int) -> int:
    conn = db_conn()
    cur = conn.cursor()
    cur.execute("SELECT consult_mode FROM users WHERE chat_id = ?", (chat_id,))
    row = cur.fetchone()
    conn.close()
    return (row[0] if row else 0) or 0

def ai_reply(text: str, user_row) -> str:
    t = text.lower()
    name = user_row[1] if user_row else "Do'st"
    issue = user_row[6] if user_row else None
    product = user_row[5] if user_row else "Painnoll"
    if any(k in t for k in ["oshqozon", "hazm", "kislota", "gaz", "qorin"]):
        return f"Assalomu alaykum, {name}. Men Nutresolog Sardor Xasanovich. Oshqozon va hazm uchun kunlik ovqatni yengil tuting, ko'p yog'li va achchiq ovqatlardan saqlaning. {product} ni belgilangan vaqtda qabul qiling, suvni yetarli iching."
    if any(k in t for k in ["bo'g'im", "suyak", "og'riq", "artrit"]):
        return f"{name}, bo'g'imlar uchun mikroharakatlar va cho'zilish mashqlari tavsiya etaman. Kalsiy va D vitamini boy ovqatlar iste'mol qiling. {product} ni 08:00, 13:00, 19:00 da muntazam iching."
    if any(k in t for k in ["prostata", "siydik", "erkak"]):
        return f"{name}, prostata salomatligi uchun yurish va to'yimli oqsil manbalari foydali. Suvni ko'proq iching, kechqurun tuz va yog'ni kamaytiring. {product} qabulini davom ettiring."
    if any(k in t for k in ["detoks", "vazn", "semirish", "parhez"]):
        return f"{name}, vazn nazorati uchun shakarni cheklang, tola va oqsilni ko'paytiring, har kuni 8-10 ming qadam yuring. {product} ni jadval bo'yicha iching."
    if any(k in t for k in ["qon bosim", "bosim", "gipertoniya"]):
        return f"{name}, qon bosimi uchun tuzni kamaytiring, stressni boshqarishga e'tibor bering, kundalik yurish qiling. {product} ni belgilangan dozada qabul qiling."
    if any(k in t for k in ["shakar", "qand", "diabet"]):
        return f"{name}, shakarni barqaror ushlab turish uchun porsiya nazorati va past glikemik indeksli ovqatlar tanlang. {product} ni ovqat oldi suv bilan iching."
    s = simple_meal_suggestion(issue)
    return f"{name}, savolingiz uchun rahmat. Men Nutresolog Sardor Xasanovich. Siz uchun umumiy tavsiya: {s}. Agar aniq alomat bo'lsa, batafsil yozing."

def simple_meal_suggestion(issue: str):
    if issue and "Oshqozon" in issue:
        return "Yengil sho'rva, jo'xori, kam yog'li ovqatlar."
    if issue and "Prostata" in issue:
        return "Suvni ko'proq iching, to'yimli oqsil (baliq, tovuq)."
    if issue and "Detoks" in issue:
        return "Sabzavot, meva, kam yog'li ovqatlar."
    if issue and "Suyak" in issue:
        return "Kalsiyga boy ovqatlar, yog'siz sut mahsulotlari, yashil bargli sabzavotlar."
    return "Muvozanatli ovqatlaning: oqsil, tolalar va suv."

def _adjust_hour(h: int):
    return (h + TIMEZONE_OFFSET) % 24

def send_daily_message(chat_id: int, label: str):
    try:
        user = get_user(chat_id)
        if not user:
            return
        name = user[1] or "Do'st"
        week = user[8] if user[8] is not None else 1
        dose = 1 if week == 1 else 2
        issue = user[6]
        text = f"🌿 Assalomu alaykum, {name}!\n\n"
        text += f"{label} tavsiya:\n"
        text += f"• Mahsulotingiz: {user[5]}\n"
        text += f"• Muvaffaqiyat uchun doz: {dose} kapsula (har doim ko'rsatilgan vaqtda)\n\n"
        text += "🍽 Bugungi ovqatlanish tavsiyasi: {0}\n\n".format(simple_meal_suggestion(issue))
        text += "👇 Amalni belgilang yoki keyinroq eslatishni so'rang."
        bot.send_message(chat_id, text, reply_markup=daily_inline)
    except Exception as e:
        logging.exception("send_daily_message error: %s", e)

def schedule_user_jobs(chat_id: int):
    jobs = [(8, "Ertalab"), (13, "Tushlik"), (19, "Kechqurun")]
    for h, label in jobs:
        adj = _adjust_hour(h)
        job_id = f"{chat_id}-{h}"
        try:
            existing = scheduler.get_job(job_id)
            if existing:
                scheduler.remove_job(job_id)
        except Exception:
            pass
        scheduler.add_job(send_daily_message, "cron", hour=adj, minute=0, second=0, args=[chat_id, label], id=job_id, replace_existing=True)

def get_progress_stats(chat_id: int):
    conn = db_conn()
    cur = conn.cursor()
    cur.execute("SELECT SUM(done) as d, COUNT(*) as c FROM progress WHERE chat_id = ?", (chat_id,))
    row = cur.fetchone()
    conn.close()
    done = row[0] or 0
    total = row[1] or 0
    return done, total

@bot.message_handler(commands=["start"])
def start_handler(message: types.Message):
    init_db()
    chat_id = message.chat.id
    u = get_user(chat_id)
    if not u:
        name = message.from_user.first_name or "Do'st"
        add_user(chat_id, name, None, None, None, "Painnoll", None)
    schedule_user_jobs(chat_id)
    text = "Assalomu alaykum! Painnoll yordamchi botiga xush kelibsiz."
    bot.send_message(chat_id, text, reply_markup=main_kb)

@bot.message_handler(commands=["admin"])
def admin_entry(message: types.Message):
    if message.chat.id in ADMIN_IDS:
        bot.send_message(message.chat.id, "Admin panel", reply_markup=admin_kb)
    else:
        bot.send_message(message.chat.id, "Kirish rad etildi.")

@bot.message_handler(func=lambda m: m.text == "👥 Foydalanuvchilar")
def admin_users(message: types.Message):
    if message.chat.id not in ADMIN_IDS:
        return
    ids = list_user_ids()
    bot.send_message(message.chat.id, f"Foydalanuvchilar soni: {len(ids)}")
    for cid in ids[:20]:
        u = get_user(cid)
        if u:
            bot.send_message(message.chat.id, f"{cid} | {u[1]} | {u[5] or '-'} | {u[6] or '-'}")

@bot.message_handler(func=lambda m: m.text == "📈 Statistika")
def admin_stats(message: types.Message):
    if message.chat.id not in ADMIN_IDS:
        return
    ids = list_user_ids()
    total = len(ids)
    done_total = 0
    logs_total = 0
    for cid in ids:
        d, t = get_progress_stats(cid)
        done_total += d
        logs_total += t
    bot.send_message(message.chat.id, f"Umumiy foydalanuvchilar: {total}\nAmallar: {done_total}/{logs_total}")

@bot.message_handler(func=lambda m: m.text == "📣 Anons yuborish")
def admin_broadcast_start(message: types.Message):
    if message.chat.id not in ADMIN_IDS:
        return
    admin_modes[message.chat.id] = "broadcast"
    bot.send_message(message.chat.id, "Anons matnini yuboring:")

@bot.message_handler(func=lambda m: admin_modes.get(m.chat.id) == "broadcast")
def admin_broadcast_do(message: types.Message):
    if message.chat.id not in ADMIN_IDS:
        return
    text = message.text
    ids = list_user_ids()
    cnt = 0
    for cid in ids:
        try:
            bot.send_message(cid, text)
            cnt += 1
        except Exception:
            pass
    admin_modes.pop(message.chat.id, None)
    bot.send_message(message.chat.id, f"Yuborildi: {cnt}")

@bot.message_handler(func=lambda m: m.text == "💊 Mahsulotlar")
def products_menu(message: types.Message):
    bot.send_message(message.chat.id, "Mahsulotni tanlang:", reply_markup=product_kb)

@bot.message_handler(func=lambda m: m.text in {"🌿 Painnoll", "🍃 BioDetox", "💪 VitaPro", "🔬 NutraMax"})
def product_set(message: types.Message):
    chat_id = message.chat.id
    update_user_field(chat_id, "product", message.text.replace("🌿 ", "").replace("🍃 ", "").replace("💪 ", "").replace("🔬 ", ""))
    schedule_user_jobs(chat_id)
    bot.send_message(chat_id, "Registratsiya tugadi. Rejalashtirish yoqildi.", reply_markup=main_kb)

@bot.message_handler(func=lambda m: m.text == "📝 Mening profilim")
def my_profile(message: types.Message):
    u = get_user(message.chat.id)
    if not u:
        bot.send_message(message.chat.id, "Profil topilmadi.")
        return
    name, age, weight, height, product, issue, week = u[1], u[2], u[3], u[4], u[5], u[6], u[8]
    text = (
        f"Ism: {name}\n"
        f"Yosh: {age or '-'}\n"
        f"Vazn: {weight or '-'}\n"
        f"Bo'y: {height or '-'}\n"
        f"Mahsulot: {product or '-'}\n"
        f"Muammo: {issue or '-'}\n"
        f"Hafta: {week or 1}"
    )
    bot.send_message(message.chat.id, text, reply_markup=issue_kb)

@bot.message_handler(func=lambda m: m.text == "🩺 Registratsiya")
def start_registration(message: types.Message):
    msg = bot.send_message(message.chat.id, "Ismingizni kiriting:")
    bot.register_next_step_handler(msg, reg_name)

def reg_name(message: types.Message):
    name = message.text.strip()
    add_user(message.chat.id, name)
    msg = bot.send_message(message.chat.id, "Yoshingizni kiriting (yil):")
    bot.register_next_step_handler(msg, reg_age)

def reg_age(message: types.Message):
    try:
        age = int(message.text.strip())
    except Exception:
        msg = bot.send_message(message.chat.id, "Yosh noto'g'ri. Raqam kiriting:")
        bot.register_next_step_handler(msg, reg_age)
        return
    update_user_field(message.chat.id, "age", age)
    msg = bot.send_message(message.chat.id, "Vazningizni kiriting (kg):")
    bot.register_next_step_handler(msg, reg_weight)

def reg_weight(message: types.Message):
    try:
        weight = float(message.text.strip().replace(',', '.'))
    except Exception:
        msg = bot.send_message(message.chat.id, "Vazn noto'g'ri. Raqam kiriting:")
        bot.register_next_step_handler(msg, reg_weight)
        return
    update_user_field(message.chat.id, "weight", weight)
    msg = bot.send_message(message.chat.id, "Bo'yingizni kiriting (sm):")
    bot.register_next_step_handler(msg, reg_height)

def reg_height(message: types.Message):
    try:
        height = float(message.text.strip().replace(',', '.'))
    except Exception:
        msg = bot.send_message(message.chat.id, "Bo'y noto'g'ri. Raqam kiriting:")
        bot.register_next_step_handler(msg, reg_height)
        return
    update_user_field(message.chat.id, "height", height)
    bot.send_message(message.chat.id, "Muammo turini tanlang:", reply_markup=issue_kb)

@bot.message_handler(func=lambda m: m.text in {"🦵 Suyak va bo'g'imlar", "🍽 Oshqozon / hazm", "🧔 Prostata", "🍋 Detoks / vazn"})
def issue_set(message: types.Message):
    chat_id = message.chat.id
    update_user_field(chat_id, "issue", message.text)
    bot.send_message(chat_id, "Mahsulotni tanlang:", reply_markup=product_kb)

@bot.message_handler(func=lambda m: m.text == "🍽 Ovqatlanish")
def meals_info(message: types.Message):
    u = get_user(message.chat.id)
    s = simple_meal_suggestion(u[6] if u else None)
    bot.send_message(message.chat.id, f"Bugungi tavsiya: {s}", reply_markup=main_kb)

@bot.message_handler(func=lambda m: m.text == "📊 Natijam")
def my_stats(message: types.Message):
    d, t = get_progress_stats(message.chat.id)
    bot.send_message(message.chat.id, f"Bajarilgan amal: {d}/{t}")

@bot.message_handler(func=lambda m: m.text == "📞 Bog'lanish")
def contact_info(message: types.Message):
    set_consult_mode(message.chat.id, True)
    bot.send_message(message.chat.id, "Men Nutresolog Sardor Xasanovich. Savolingizni yozing va javob beraman.")

@bot.message_handler(func=lambda m: m.text == "🎁 Aksiya")
def promo_info(message: types.Message):
    bot.send_message(message.chat.id, "Aksiya: Bugun buyurtmaga maxsus chegirma mavjud.")

@bot.message_handler(func=lambda m: m.text not in {"📝 Mening profilim", "🍽 Ovqatlanish", "💊 Mahsulotlar", "📊 Natijam", "📞 Bog'lanish", "🎁 Aksiya", "⬅️ Orqaga", "🩺 Registratsiya", "👥 Foydalanuvchilar", "📈 Statistika", "📣 Anons yuborish"})
def ai_catch_all(message: types.Message):
    if get_consult_mode(message.chat.id):
        u = get_user(message.chat.id)
        ans = ai_reply(message.text, u)
        bot.send_message(message.chat.id, ans)

@bot.message_handler(content_types=["photo"]) 
def on_photo(message: types.Message):
    cap = message.caption or ""
    text = f"Rasm: {message.chat.id} | {message.from_user.first_name or ''} | {cap}"
    for aid in ADMIN_IDS:
        try:
            bot.send_photo(aid, message.photo[-1].file_id, caption=text)
        except Exception:
            pass
    bot.send_message(message.chat.id, "Rasm qabul qilindi.")

@bot.message_handler(content_types=["video"]) 
def on_video(message: types.Message):
    cap = message.caption or ""
    text = f"Video: {message.chat.id} | {message.from_user.first_name or ''} | {cap}"
    for aid in ADMIN_IDS:
        try:
            bot.send_video(aid, message.video.file_id, caption=text)
        except Exception:
            pass
    bot.send_message(message.chat.id, "Video qabul qilindi.")

@bot.message_handler(func=lambda m: m.text == "⬅️ Orqaga")
def back_to_main(message: types.Message):
    bot.send_message(message.chat.id, "Asosiy menyu.", reply_markup=main_kb)
    set_consult_mode(message.chat.id, False)

@bot.callback_query_handler(func=lambda c: c.data in {"done", "remind_later"})
def inline_actions(callback_query: types.CallbackQuery):
    chat_id = callback_query.message.chat.id
    text = callback_query.message.text or ""
    label = ""
    if "Ertalab" in text:
        label = "Ertalab"
    elif "Tushlik" in text:
        label = "Tushlik"
    elif "Kechqurun" in text:
        label = "Kechqurun"
    else:
        label = "Eslatma"
    if callback_query.data == "done":
        log_progress(chat_id, label, True)
        bot.answer_callback_query(callback_query.id, "Bajarildi")
    else:
        run_at = datetime.utcnow() + timedelta(minutes=30)
        scheduler.add_job(send_daily_message, "date", run_date=run_at, args=[chat_id, label])
        log_progress(chat_id, label, False)
        bot.answer_callback_query(callback_query.id, "Keyinroq eslatiladi")

def start_scheduler_for_all():
    for cid in list_user_ids():
        schedule_user_jobs(cid)
    try:
        scheduler.start()
    except Exception:
        pass

def run_bot():
    try:
        bot.delete_webhook(drop_pending_updates=True)
    except Exception as e:
        logging.warning("delete_webhook failed: %s", e)
    while True:
        try:
            bot.infinity_polling(
                skip_pending=True,
                timeout=20,
                long_polling_timeout=20,
                allowed_updates=["message", "callback_query"],
            )
        except Exception as e:
            logging.exception("polling error: %s", e)
            time.sleep(10)

def run_webhook(app_url: str):
    try:
        import json
        from fastapi import FastAPI, Request
        import uvicorn
    except Exception:
        logging.error("WebHook rejimi uchun fastapi/uvicorn kerak. Iltimos o'rnating.")
        return

    webhook_url = app_url.rstrip("/") + "/webhook"
    try:
        try:
            bot.delete_webhook(drop_pending_updates=True)
        except Exception:
            pass
        bot.set_webhook(webhook_url)
        logging.info("Webhook set: %s", webhook_url)
    except Exception as e:
        logging.exception("set_webhook failed: %s", e)

    app = FastAPI()

    @app.get("/")
    def root():
        return {"status": "ok"}

    @app.post("/webhook")
    async def telegram_webhook(req: Request):
        payload = await req.body()
        try:
            update = telebot.types.Update.de_json(payload.decode("utf-8"))
            bot.process_new_updates([update])
        except Exception:
            # Ba’zi hostinglarda request.json kerak bo‘ladi
            try:
                data = await req.json()
                update = telebot.types.Update.de_json(json.dumps(data))
                bot.process_new_updates([update])
            except Exception as e:
                logging.exception("Webhook parse error: %s", e)
        return {"ok": True}

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8080")))

if __name__ == "__main__":
    init_db()
    start_scheduler_for_all()
    app_url = os.getenv("APP_URL") or os.getenv("RENDER_EXTERNAL_URL") or os.getenv("RAILWAY_PUBLIC_DOMAIN") or os.getenv("RAILWAY_STATIC_URL")
    if app_url:
        run_webhook(app_url)
    else:
        run_bot()