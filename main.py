"""
Telegram Giveaway Bot v5.2 Ultimate — In-Bot Channel Template Editor & Fixed SQLite
pip install -U aiogram
"""
import asyncio
import csv
import hashlib
import html
import io
import logging
import os
import random
import re
import secrets
import sqlite3
import time
from contextlib import contextmanager
from urllib.parse import quote

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    BufferedInputFile, CallbackQuery, InlineKeyboardButton,
    InlineKeyboardMarkup, Message, ReplyKeyboardMarkup, KeyboardButton,
    ReplyKeyboardRemove
)

# ---------------- تنظیمات اصلی ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN", "PUT_YOUR_TOKEN_HERE")
ADMIN_IDS = {int(x) for x in os.getenv("ADMIN_IDS", "0").split(",") if x.strip()}
DB_PATH = os.getenv("DB_PATH", "giveaway_v5.db")
REMIND_BEFORE = 3600   # ثانیه (۱ ساعت)
TICK = 15              # ثانیه
DM_DELAY = 0.06        # ثانیه بین DM

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("giveaway")

# =====================================================
#  ⚙️ متون پیش‌فرض کانال (قابل ویرایش از داخل ربات)
# =====================================================
DEFAULT_TEMPLATES = {
    "post_header": "🎉 <b>#قرعه_کشی | {title}</b>\n🏛 ────────────────────",
    "post_single_prize": "🎁 <b>جایزه:</b> {prize}",
    "post_multi_prize_title": "🎁 <b>لیست جوایز:</b>",
    "post_multi_prize_item": "  ├ رتبه {rank}: {prize}",
    "post_winners_count": "👥 <b>تعداد برندگان:</b> {count} نفر",
    "post_ends_at": "⏰ <b>مهلت شرکت:</b> تا {ends_at}",
    "post_channels": "📢 <b>کانال‌های حامی:</b> {channels}",
    "post_min_invites": "👫 <b>شرط ورود:</b> حداقل {invites} دعوت (هر دعوت = ۱ شانس اضافه 🎟)",
    "post_footer": "🏛 ────────────────────\n👇 <b>جهت شرکت و دریافت لینک اختصاصی روی دکمه زیر بزنید:</b>",
    "start_notice": "🚀 <b>قرعه‌کشی «{title}» رسماً شروع شد!</b>\n\nهم‌اکنون می‌توانید با کلیک روی دکمه پست بالا وارد شوید.",
    "reminder_notice": "⏰ <b>فقط ۱ ساعت تا پایان قرعه‌کشی «{title}» باقیست!</b>\n\n🔥 فرصت را از دست ندهید! اگر هنوز شرکت نکرده‌اید یا می‌خواهید شانس خود را بیشتر کنید روی دکمه زیر بزنید 👇",
    "reminder_btn_text": "🎁 شرکت در قرعه‌کشی / افزودن شانس",
    "end_notice": "🔒 <b>مهلت شرکت در قرعه‌کشی «{title}» به پایان رسید!</b>\n\n⏳ هم‌اکنون قرعه‌کشی و بررسی استعلام اعضا در حال انجام است...",
    "live_draw_start": "🎲 <b>گردونه شانس در حال چرخیدن است...</b>\n\n⏳ لطفاً شکیبا باشید...",
    "live_draw_step": "🎲 <b>در حال قرعه‌کشی: {title}</b>\n\n🎰 انتخاب از میان واجدین شرایط: <b>{name}</b>",
    "results_header": "🏆 <b>نتایج رسمی قرعه‌کشی: {title}</b>\n👑 ════════════════════\n👥 <b>کل واجدین شرایط:</b> {total_users} نفر\n",
    "results_winner_item": "🥇 <b>مقام {rank}:</b> {prize}\n└ 👤 برنده: <a href='tg://user?id={user_id}'>{username}</a> ({invites} دعوت)\n",
    "results_footer": "👑 ════════════════════\n🔐 <b>کد شفافیت (SHA256):</b>\n<code>{digest}</code>\n\n✨ <i>تبریک به برندگان عزیز! جهت دریافت جایزه به پیوی مراجعه کنید.</i>",
    "results_no_winners": "🎁 <b>قرعه‌کشی: {title}</b>\n\n😕 متأسفانه برنده واجد شرایطی یافت نشد.",
    "sponsor_notice": "📢 <b>با تشکر ویژه از اسپانسر محترم این قرعه‌کشی:</b>\n\n🔹 <b>{sponsor_name}</b>\nجهت مشاهده خدمات و حمایت از اسپانسر روی دکمه زیر کلیک کنید 👇",
    "sponsor_btn_text": "🔗 ورود به {sponsor_name}",
}

TEMPLATE_LABELS = {
    "post_header": "📌 سربرگ پست قرعه‌کشی",
    "post_single_prize": "🎁 متن تک جایزه‌ای",
    "post_multi_prize_title": "🎁 تیتر چند جایزه‌ای",
    "post_winners_count": "👥 تعداد برندگان",
    "post_ends_at": "⏰ زمان پایان",
    "post_channels": "📢 کانال‌های حامی",
    "post_min_invites": "👫 شرط حداقل دعوت",
    "post_footer": "👇 پاورقی پست قرعه‌کشی",
    "start_notice": "🚀 پیام شروع رسمی",
    "reminder_notice": "⏰ پیام یادآوری (۱ ساعت مانده)",
    "reminder_btn_text": "🔘 دکمه پیام یادآوری",
    "end_notice": "🔒 پیام اتمام مهلت شرکت",
    "live_draw_start": "🎲 شروع لایو قرعه‌کشی",
    "live_draw_step": "🎰 انیمیشن لایو قرعه‌کشی",
    "results_header": "🏆 سربرگ اعلام نتایج",
    "results_winner_item": "🥇 نمایش برنده در لیست نتایج",
    "results_footer": "🔐 پاورقی اعلام نتایج و هش کد",
    "results_no_winners": "😕 پیام عدم وجود برنده",
    "sponsor_notice": "📢 متن تشکر از اسپانسر",
    "sponsor_btn_text": "🔗 دکمه لینک اسپانسر"
}

admin_router = Router()
user_router = Router()
admin_router.message.filter(F.from_user.id.in_(ADMIN_IDS))
admin_router.callback_query.filter(F.from_user.id.in_(ADMIN_IDS))

DIRTY: set[int] = set()
REMINDED: set[int] = set()
BG_TASKS: set[asyncio.Task] = set()
DRAWING: set[int] = set()


def is_admin(uid: int) -> bool:
    return uid in ADMIN_IDS


def spawn(coro) -> asyncio.Task:
    t = asyncio.create_task(coro)
    BG_TASKS.add(t)
    t.add_done_callback(BG_TASKS.discard)
    return t


def btn(text: str, **kw) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, **kw)


def kb(*rows) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[list(r) for r in rows])


# ---------------- دیتابیس ----------------
@contextmanager
def db(write: bool = False):
    conn = sqlite3.connect(DB_PATH, timeout=15, isolation_level=None)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA synchronous=NORMAL")
        if write:
            conn.execute("BEGIN IMMEDIATE")
        yield conn
        if write:
            try:
                conn.execute("COMMIT")
            except sqlite3.OperationalError:
                pass
    except Exception:
        if write:
            try:
                conn.execute("ROLLBACK")
            except Exception:
                pass
        raise
    finally:
        conn.close()


def init_db():
    with db(write=True) as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS giveaways (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            prizes TEXT NOT NULL,
            prize_codes TEXT,
            banner_url TEXT,
            winners_count INTEGER NOT NULL,
            post_channel TEXT NOT NULL,
            message_id INTEGER,
            start_at INTEGER NOT NULL DEFAULT 0,
            ends_at INTEGER NOT NULL,
            min_invites INTEGER NOT NULL DEFAULT 0,
            sponsor_text TEXT,
            sponsor_url TEXT,
            captcha INTEGER NOT NULL DEFAULT 1,
            req_phone INTEGER NOT NULL DEFAULT 0,
            seed TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS gw_channels (
            giveaway_id INTEGER NOT NULL,
            channel TEXT NOT NULL,
            PRIMARY KEY (giveaway_id, channel)
        );
        CREATE TABLE IF NOT EXISTS entrants (
            giveaway_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            username TEXT,
            full_name TEXT,
            captcha_ok INTEGER NOT NULL DEFAULT 0,
            phone_ok INTEGER NOT NULL DEFAULT 0,
            joined_at INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (giveaway_id, user_id)
        );
        CREATE TABLE IF NOT EXISTS referrals (
            giveaway_id INTEGER NOT NULL,
            inviter_id INTEGER NOT NULL,
            invited_id INTEGER NOT NULL,
            verified INTEGER NOT NULL DEFAULT 0,
            created_at INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (giveaway_id, invited_id)
        );
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            phone_number TEXT,
            lang TEXT NOT NULL DEFAULT 'fa',
            first_seen INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS templates (
            key TEXT PRIMARY KEY,
            val TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_ref_inviter ON referrals(giveaway_id, inviter_id, verified);
        CREATE INDEX IF NOT EXISTS idx_ent_gw ON entrants(giveaway_id, captcha_ok);
        CREATE INDEX IF NOT EXISTS idx_gw_status ON giveaways(status, ends_at);
        """)
        for key, val in DEFAULT_TEMPLATES.items():
            c.execute("INSERT OR IGNORE INTO templates (key, val) VALUES (?, ?)", (key, val))


def get_template(key: str) -> str:
    with db() as c:
        r = c.execute("SELECT val FROM templates WHERE key=?", (key,)).fetchone()
        return r["val"] if r else DEFAULT_TEMPLATES.get(key, "")


def set_template(key: str, val: str):
    with db(write=True) as c:
        c.execute("INSERT INTO templates (key, val) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET val=excluded.val", (key, val))


def get_gw(gid: int):
    with db() as c:
        return c.execute("SELECT * FROM giveaways WHERE id=?", (gid,)).fetchone()


def gw_channels(gid: int) -> list[str]:
    with db() as c:
        return [r["channel"] for r in c.execute("SELECT channel FROM gw_channels WHERE giveaway_id=?", (gid,))]


def invites_of(gid: int, uid: int) -> int:
    with db() as c:
        r = c.execute("SELECT COUNT(*) AS n FROM referrals WHERE giveaway_id=? AND inviter_id=? AND verified=1", (gid, uid)).fetchone()
        return r["n"] if r else 0


def eligible(gid: int) -> list:
    g = get_gw(gid)
    if not g:
        return []
    with db() as c:
        phone_clause = "AND e.phone_ok = 1" if g["req_phone"] else ""
        return c.execute(f"""
            SELECT e.* FROM entrants e
            WHERE e.giveaway_id = ?1 AND e.captcha_ok = 1 {phone_clause}
              AND (
                SELECT COUNT(*) FROM referrals r
                WHERE r.giveaway_id = e.giveaway_id
                  AND r.inviter_id = e.user_id AND r.verified = 1
              ) >= ?2
        """, (gid, g["min_invites"])).fetchall()


def n_entrants(gid: int) -> int:
    with db() as c:
        r = c.execute("SELECT COUNT(*) AS n FROM entrants WHERE giveaway_id=?", (gid,)).fetchone()
        return r["n"] if r else 0


def leaderboard(gid: int, limit: int = 10) -> list:
    with db() as c:
        return c.execute("""
            SELECT r.inviter_id, COUNT(*) AS c
            FROM referrals r
            JOIN entrants e ON e.giveaway_id = r.giveaway_id AND e.user_id = r.inviter_id AND e.captcha_ok = 1
            WHERE r.giveaway_id = ? AND r.verified = 1
            GROUP BY r.inviter_id
            ORDER BY c DESC LIMIT ?
        """, (gid, limit)).fetchall()


def get_lang(uid: int) -> str:
    with db() as c:
        r = c.execute("SELECT lang FROM users WHERE user_id=?", (uid,)).fetchone()
        return r["lang"] if r else "fa"


def set_lang(uid: int, lang: str):
    with db(write=True) as c:
        c.execute("INSERT INTO users (user_id, lang) VALUES (?,?) ON CONFLICT(user_id) DO UPDATE SET lang=excluded.lang", (uid, lang))


def ensure_user(uid: int):
    with db(write=True) as c:
        c.execute("INSERT OR IGNORE INTO users (user_id, first_seen) VALUES (?, ?)", (uid, int(time.time())))


# ---------------- i18n ----------------
T = {
    "fa": {
        "must_join": "📌 <b>جهت ثبت‌نام در قرعه‌کشی، ابتدا در کانال‌های زیر عضو شوید:</b>\n\nپس از عضویت، روی دکمه بررسی کلیک کنید.",
        "joined": "🔄 بررسی عضویت",
        "captcha": "🛡 <b>تأیید هویت و امنیت</b>\n\nبرای جلوگیری از ورود ربات‌ها، لطفاً روی دکمه زیر بزنید:",
        "captcha_btn": "🤖 من ربات نیستم",
        "phone_req": "📱 <b>احراز هویت شماره تلفن</b>\n\nبرای شرکت در این قرعه‌کشی، لطفاً با کلیک روی دکمه زیر شماره خود را به اشتراک بگذارید:",
        "phone_btn": "📱 ارسال شماره تلفن جهت احراز هویت",
        "finished": "🚫 این قرعه‌کشی به پایان رسیده یا معتبر نمی‌باشد.",
        "captcha_ok": "✅ هویت شما با موفقیت تأیید شد!",
        "no_change": "هنوز تغییری ایجاد نشده است 🙂",
        "bad_link": "❌ لینک ورود نامعتبر است.",
        "welcome": "👋 <b>به ربات برگزاری قرعه‌کشی خوش آمدید!</b>\n\nبرای شرکت، روی دکمه‌های شیشه‌ای زیر پست‌های کانال کلیک کنید.\n/lang fa | en",
    },
    "en": {
        "must_join": "📌 <b>To enter, please join the following channels first:</b>",
        "joined": "🔄 Verify Membership",
        "captcha": "🛡 <b>Security Verification</b>\n\nPlease confirm you are human:",
        "captcha_btn": "🤖 I'm not a bot",
        "phone_req": "📱 <b>Phone Verification</b>\n\nPlease share your contact to participate:",
        "phone_btn": "📱 Share Contact",
        "finished": "🚫 This giveaway has ended.",
        "captcha_ok": "✅ Verification successful!",
        "no_change": "No changes detected 🙂",
        "bad_link": "❌ Invalid entry link.",
        "welcome": "👋 <b>Welcome to Giveaway Bot!</b>\n\nClick the button under channel posts to participate.\n/lang fa | en",
    },
}


def t(uid: int, key: str, **kw) -> str:
    s = T.get(get_lang(uid), T["fa"]).get(key, key)
    try:
        return s.format(**kw)
    except (KeyError, IndexError):
        return s


def fmt_time(ts: int) -> str:
    return time.strftime("%Y-%m-%d · %H:%M", time.localtime(ts))


def post_text(g) -> str:
    lines = [get_template("post_header").format(title=html.escape(g['title']))]
    prizes = [p for p in (g["prizes"] or "").split("|") if p.strip()] or ["—"]
    
    if len(prizes) == 1:
        lines.append(get_template("post_single_prize").format(prize=html.escape(prizes[0])))
    else:
        lines.append(get_template("post_multi_prize_title"))
        for i, p in enumerate(prizes, 1):
            lines.append(get_template("post_multi_prize_item").format(rank=i, prize=html.escape(p)))

    lines.append(get_template("post_winners_count").format(count=g['winners_count']))
    lines.append(get_template("post_ends_at").format(ends_at=fmt_time(g['ends_at'])))
    
    chans = gw_channels(g["id"])
    if chans:
        lines.append(get_template("post_channels").format(channels=" ، ".join(chans)))
    if g["min_invites"]:
        lines.append(get_template("post_min_invites").format(invites=g['min_invites']))

    lines.append(get_template("post_footer"))
    return "\n".join(lines)


async def post_kb(bot: Bot, g, n: int) -> InlineKeyboardMarkup:
    me = await bot.me()
    url = f"https://t.me/{me.username}?start=g_{g['id']}"
    rows = [[btn(f"🎁 شرکت در قرعه‌کشی ({n} نفر)", url=url)]]
    if g["sponsor_url"]:
        label = g["sponsor_text"] or "اسپانسر ویژه"
        rows.append([btn(f"📣 {label}", url=g["sponsor_url"])])
    return kb(*rows)


async def send_post_msg(bot: Bot, chat_id: str, g, n: int):
    text = post_text(g)
    markup = await post_kb(bot, g, n)
    if g["banner_url"]:
        return await bot.send_photo(chat_id, photo=g["banner_url"], caption=text, reply_markup=markup)
    return await bot.send_message(chat_id, text, reply_markup=markup)


# ---------------- عضویت ----------------
async def missing_channels(bot: Bot, gid: int, uid: int) -> list[str]:
    miss = []
    for ch in gw_channels(gid):
        try:
            m = await bot.get_chat_member(ch, uid)
            status = getattr(m, "status", None)
            is_member = getattr(m, "is_member", False)
            left = (status in ("left", "kicked") or (status == "restricted" and not is_member))
            if left:
                miss.append(ch)
        except TelegramBadRequest:
            miss.append(ch)
        except Exception as e:
            log.warning("get_chat_member(%s, %s): %s", ch, uid, e)
            miss.append(ch)
    return miss


async def notify_inviter(bot: Bot, g, inviter_id: int):
    try:
        have = invites_of(g["id"], inviter_id)
        need = g["min_invites"]
        tickets = have + 1
        msg = f"🎉 <b>یک کاربر با لینک اختصاصی شما وارد شد!</b>\n\n📊 <b>وضعیت دعوت‌ها:</b> {have}/{need}\n🎟 <b>بلیط‌های شما:</b> {tickets}"
        if have == need:
            msg += "\n\n✅ <b>تبریک! شرط حداقل دعوت شما برآورده شد و وارد قرعه‌کشی شدید.</b>"
        await bot.send_message(inviter_id, msg)
    except (TelegramBadRequest, TelegramForbiddenError):
        pass
    except Exception as e:
        log.warning("notify_inviter(%s): %s", inviter_id, e)


# ---------------- کارت شرکت ----------------
async def entry_screen(bot: Bot, gid: int, user):
    g = get_gw(gid)
    uid = user.id
    if not g or g["status"] != "active" or g["ends_at"] <= time.time():
        return t(uid, "finished"), None, None

    with db() as c:
        row = c.execute("SELECT captcha_ok, phone_ok FROM entrants WHERE giveaway_id=? AND user_id=?", (gid, uid)).fetchone()

    if g["captcha"] and (not row or not row["captcha_ok"]):
        return t(uid, "captcha"), kb([btn(t(uid, "captcha_btn"), callback_data=f"cap:{gid}")]), None

    if g["req_phone"] and (not row or not row["phone_ok"]):
        reply_kb = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text=t(uid, "phone_btn"), request_contact=True)]],
            resize_keyboard=True, one_time_keyboard=True
        )
        return t(uid, "phone_req"), None, reply_kb

    miss = await missing_channels(bot, gid, uid)
    if miss:
        rows = [[btn(f"📢 عضویت در {ch}", url=f"https://t.me/{ch.lstrip('@')}")] for ch in miss]
        rows.append([btn(t(uid, "joined"), callback_data=f"chk:{gid}")])
        return t(uid, "must_join"), kb(*rows), None

    newly_verified = False
    inviter_id = None
    with db(write=True) as c:
        cur = c.execute(
            "INSERT OR IGNORE INTO entrants (giveaway_id,user_id,username,full_name,captcha_ok,phone_ok,joined_at) VALUES (?,?,?,?,1,1,?)",
            (gid, uid, user.username, user.full_name, int(time.time())))
        new_entrant = cur.rowcount > 0

        ref = c.execute("SELECT inviter_id, verified FROM referrals WHERE giveaway_id=? AND invited_id=?", (gid, uid)).fetchone()
        if ref and not ref["verified"]:
            c.execute("UPDATE referrals SET verified=1 WHERE giveaway_id=? AND invited_id=? AND verified=0", (gid, uid))
            newly_verified = True
            inviter_id = ref["inviter_id"]

    if newly_verified and inviter_id:
        spawn(notify_inviter(bot, g, inviter_id))
    if new_entrant or newly_verified:
        DIRTY.add(gid)

    need = g["min_invites"]
    have = invites_of(gid, uid)
    tickets = have + 1

    me = await bot.me()
    link = f"https://t.me/{me.username}?start=g_{gid}_{uid}"
    share = ("https://t.me/share/url?url=" + quote(link) + "&text=" + quote(f"🎁 در قرعه‌کشی بزرگ «{g['title']}» شرکت کن!"))

    card = [
        f"🎯 <b>کارت ورود به قرعه‌کشی: {html.escape(g['title'])}</b>",
        "📋 ════════════════",
        f"👤 <b>شرکت‌کننده:</b> {html.escape(user.full_name or 'کاربر')}",
        f"🎟 <b>کل بلیط‌های شما:</b> <code>{tickets}</code> شانس",
    ]

    if need > 0:
        status_icon = "✅" if have >= need else "⏳"
        card.append(f"👫 <b>دعوت‌های تأییدشده:</b> {have} از {need} {status_icon}")
        if have < need:
            card.append(f"⚠️ <i>برای ورود باید {need - have} نفر دیگر را دعوت کنید.</i>")
        else:
            card.append("🎉 <i>شرط دعوت برآورده شد!</i>")

    card += [
        "📋 ════════════════",
        "🔗 <b>لینک اختصاصی دعوت شما:</b>",
        f"<code>{link}</code>",
        "\n💡 <i>هر دعوت موفق = ۱ بلیط شانس بیشتر</i>"
    ]

    buttons = [[btn("📤 ارسال لینک برای دوستان", url=share)]]
    if need > 0:
        buttons.append([btn("🔄 بروزرسانی وضعیت", callback_data=f"chk:{gid}")])
    buttons.append([btn("🏆 جدول ۱۰ دعوت‌کننده برتر", callback_data=f"top:{gid}")])

    return "\n".join(card), kb(*buttons), None


# ---------------- قرعه‌کشی و اعلانات کانال ----------------
def build_pool(users: list) -> list:
    pool = []
    for u in users:
        w = 1 + invites_of(u["giveaway_id"], u["user_id"])
        pool.extend([u["user_id"]] * max(w, 1))
    return pool


async def finish_giveaway(bot: Bot, gid: int):
    if gid in DRAWING:
        return
    DRAWING.add(gid)
    try:
        with db(write=True) as c:
            cur = c.execute("UPDATE giveaways SET status='finished' WHERE id=? AND status='active'", (gid,))
            if cur.rowcount == 0:
                return
        g = get_gw(gid)
        if not g:
            return

        title = html.escape(g["title"])

        try:
            await bot.send_message(g["post_channel"], get_template("end_notice").format(title=title))
        except TelegramBadRequest as e:
            log.warning("End notice error: %s", e)

        users = list(eligible(gid))
        prizes = [p for p in (g["prizes"] or "").split("|") if p.strip()] or ["—"]
        prize_codes = [c.strip() for c in (g["prize_codes"] or "").split("|") if c.strip()]

        live_msg = None
        if users:
            try:
                live_msg = await bot.send_message(g["post_channel"], get_template("live_draw_start"))
                for _ in range(3):
                    await asyncio.sleep(1)
                    sample = random.choice(users)
                    name = sample["full_name"] or "کاربر"
                    try:
                        await bot.edit_message_text(
                            get_template("live_draw_step").format(title=title, name=html.escape(name)),
                            chat_id=g["post_channel"],
                            message_id=live_msg.message_id)
                    except TelegramBadRequest:
                        pass
            except TelegramBadRequest as e:
                log.warning("live draw: %s", e)

        winners = []
        if users:
            pool_uid = build_pool(users)
            by_uid = {u["user_id"]: u for u in users}
            seen: set[int] = set()
            need = min(g["winners_count"], len(users))

            while len(winners) < need and pool_uid:
                pick_uid = random.choice(pool_uid)
                pool_uid = [x for x in pool_uid if x != pick_uid]
                if pick_uid in seen:
                    continue
                seen.add(pick_uid)
                pick = by_uid.get(pick_uid)
                if not pick:
                    continue
                miss = await missing_channels(bot, gid, pick_uid)
                if miss:
                    log.info("reroll uid=%s left=%s", pick_uid, miss)
                    continue
                winners.append(pick)

        ids = ",".join(str(u["user_id"]) for u in users)
        payload = f"{gid}|{int(time.time())}|{g['seed'] or ''}|{ids}".encode()
        digest = hashlib.sha256(payload).hexdigest()

        if not winners:
            text = get_template("results_no_winners").format(title=title)
        else:
            lines = [get_template("results_header").format(title=title, total_users=len(users))]
            for i, w in enumerate(winners):
                uname = (f"@{w['username']}" if w["username"] else html.escape(w["full_name"] or "کاربر"))
                prize = prizes[i] if i < len(prizes) else prizes[-1]
                inv = invites_of(gid, w["user_id"])
                lines.append(get_template("results_winner_item").format(rank=i+1, prize=html.escape(prize), user_id=w['user_id'], username=uname, invites=inv))
            lines.append(get_template("results_footer").format(digest=digest))
            text = "".join(lines)

        sent_ok = False
        if live_msg:
            try:
                await bot.edit_message_text(text, chat_id=g["post_channel"], message_id=live_msg.message_id)
                sent_ok = True
            except TelegramBadRequest as e:
                log.warning("result edit failed: %s", e)
        if not sent_ok:
            try:
                await bot.send_message(g["post_channel"], text)
            except TelegramBadRequest as e:
                log.error("result send failed: %s", e)

        if g["sponsor_url"]:
            try:
                sp_label = g["sponsor_text"] or "اسپانسر برنامه"
                await bot.send_message(
                    g["post_channel"],
                    get_template("sponsor_notice").format(sponsor_name=html.escape(sp_label)),
                    reply_markup=kb([btn(get_template("sponsor_btn_text").format(sponsor_name=sp_label), url=g["sponsor_url"])])
                )
            except TelegramBadRequest:
                pass

        if g["message_id"]:
            try:
                await bot.edit_message_reply_markup(chat_id=g["post_channel"], message_id=g["message_id"], reply_markup=None)
            except TelegramBadRequest:
                pass

        for i, w in enumerate(winners):
            try:
                prize = prizes[i] if i < len(prizes) else prizes[-1]
                code_text = ""
                if i < len(prize_codes):
                    code_text = f"\n🔑 <b>کد جایزه اختصاصی شما:</b> <code>{html.escape(prize_codes[i])}</code>"

                await bot.send_message(
                    w["user_id"],
                    f"🎉 <b>تبریک فوق‌العاده! شما برنده شدید!</b> 🏆\n\n🎁 <b>جایزه شما:</b> {html.escape(prize)}{code_text}\nمقام: رتبه {i+1} در قرعه‌کشی «{title}»\n\nبا تشکر از شرکت شما!")
                await asyncio.sleep(DM_DELAY)
            except (TelegramBadRequest, TelegramForbiddenError):
                pass

        REMINDED.discard(gid)
        DIRTY.discard(gid)
        log.info("finished #%s winners=%s", gid, [w["user_id"] for w in winners])
    finally:
        DRAWING.discard(gid)


async def cancel_giveaway(bot: Bot, gid: int):
    with db(write=True) as c:
        cur = c.execute("UPDATE giveaways SET status='cancelled' WHERE id=? AND status IN ('active','pending')", (gid,))
        if cur.rowcount == 0:
            return
    g = get_gw(gid)
    if not g or not g["message_id"] or g["status"] == "pending":
        return
    try:
        await bot.edit_message_text(f"🚫 <b>{html.escape(g['title'])}</b>\n\nاین قرعه‌کشی توسط مدیریت لغو شد.", chat_id=g["post_channel"], message_id=g["message_id"])
        await bot.edit_message_reply_markup(chat_id=g["post_channel"], message_id=g["message_id"], reply_markup=None)
    except TelegramBadRequest as e:
        log.warning("cancel edit: %s", e)


# ---------------- Watcher ----------------
async def watcher(bot: Bot):
    log.info("watcher started")
    while True:
        try:
            now = int(time.time())

            with db() as c:
                pend = c.execute("SELECT id FROM giveaways WHERE status='pending' AND start_at>0 AND start_at<=?", (now,)).fetchall()
            for r in pend:
                gid = r["id"]
                g = get_gw(gid)
                if not g:
                    continue
                try:
                    sent = await send_post_msg(bot, g["post_channel"], g, 0)
                    await bot.send_message(g["post_channel"], get_template("start_notice").format(title=html.escape(g['title'])))
                    with db(write=True) as c:
                        c.execute("UPDATE giveaways SET status='active', message_id=? WHERE id=? AND status='pending'", (sent.message_id, gid))
                    log.info("scheduled publish #%s", gid)
                except TelegramBadRequest as e:
                    log.error("schedule send #%s: %s", gid, e)

            with db() as c:
                broken = c.execute("SELECT id FROM giveaways WHERE status='active' AND (message_id IS NULL OR message_id=0)").fetchall()
            for r in broken:
                gid = r["id"]
                g = get_gw(gid)
                if not g:
                    continue
                try:
                    sent = await send_post_msg(bot, g["post_channel"], g, 0)
                    with db(write=True) as c:
                        c.execute("UPDATE giveaways SET message_id=? WHERE id=? AND message_id IS NULL", (sent.message_id, gid))
                except TelegramBadRequest as e:
                    log.error("fix broken #%s: %s", gid, e)

            with db() as c:
                rows = c.execute("SELECT id, ends_at FROM giveaways WHERE status='active'").fetchall()
            for r in rows:
                gid = r["id"]
                delta = r["ends_at"] - now
                if 0 < delta <= REMIND_BEFORE and gid not in REMINDED:
                    REMINDED.add(gid)
                    spawn(send_reminders(bot, gid))
                if delta <= 0:
                    spawn(finish_giveaway(bot, gid))

            for gid in list(DIRTY):
                DIRTY.discard(gid)
                g = get_gw(gid)
                if not g or g["status"] != "active" or not g["message_id"]:
                    continue
                try:
                    await bot.edit_message_reply_markup(chat_id=g["post_channel"], message_id=g["message_id"], reply_markup=await post_kb(bot, g, len(eligible(gid))))
                except TelegramBadRequest:
                    pass

            try:
                with db(write=True) as c:
                    c.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            except Exception:
                pass

        except Exception:
            log.exception("watcher error")
        await asyncio.sleep(TICK)


async def send_reminders(bot: Bot, gid: int):
    g = get_gw(gid)
    if not g:
        return

    me = await bot.me()
    url = f"https://t.me/{me.username}?start=g_{gid}"

    try:
        await bot.send_message(
            g["post_channel"],
            get_template("reminder_notice").format(title=html.escape(g['title'])),
            reply_markup=kb([btn(get_template("reminder_btn_text"), url=url)])
        )
    except TelegramBadRequest as e:
        log.warning("Channel reminder error: %s", e)

    try:
        users = eligible(gid)
        for u in users:
            try:
                await bot.send_message(
                    u["user_id"],
                    f"⏰ <b>زمان رو به پایان است!</b>\n\nفقط ۱ ساعت تا پایان قرعه‌کشی «{html.escape(g['title'])}» زمان داری.\n🎟 با دعوت از دوستانت، شانس برنده شدنت رو چند برابر کن!")
            except (TelegramBadRequest, TelegramForbiddenError):
                pass
            except Exception as e:
                log.warning("reminder %s: %s", u["user_id"], e)
            await asyncio.sleep(DM_DELAY)
    except Exception:
        log.exception("send_reminders")


# =====================================================
#                       کاربر
# =====================================================
@user_router.message(CommandStart())
async def start(m: Message, command: CommandObject, bot: Bot):
    ensure_user(m.from_user.id)
    payload = command.args or ""

    if payload.startswith("g_"):
        parts = payload.split("_")
        if len(parts) < 2 or not parts[1].isdigit():
            return await m.answer(t(m.from_user.id, "bad_link"))
        gid = int(parts[1])
        inviter = None
        if len(parts) >= 3 and parts[2].isdigit():
            inviter = int(parts[2])

        g = get_gw(gid)
        if (g and g["status"] == "active" and g["min_invites"] > 0 and inviter and inviter != m.from_user.id):
            with db(write=True) as c:
                al = c.execute("SELECT 1 FROM entrants WHERE giveaway_id=? AND user_id=?", (gid, m.from_user.id)).fetchone()
                if not al:
                    c.execute("INSERT OR IGNORE INTO referrals (giveaway_id, inviter_id, invited_id, created_at) VALUES (?,?,?,?)", (gid, inviter, m.from_user.id, int(time.time())))

        text, markup, reply_kb = await entry_screen(bot, gid, m.from_user)
        return await m.answer(text, reply_markup=reply_kb or markup)

    if is_admin(m.from_user.id):
        return await m.answer(PANEL_TEXT, reply_markup=panel_kb())
    await m.answer(t(m.from_user.id, "welcome"))


@user_router.message(F.contact)
async def contact_handler(m: Message):
    if m.contact and m.contact.user_id == m.from_user.id:
        phone = m.contact.phone_number
        with db(write=True) as c:
            c.execute("UPDATE users SET phone_number=? WHERE user_id=?", (phone, m.from_user.id))
            c.execute("UPDATE entrants SET phone_ok=1 WHERE user_id=?", (m.from_user.id,))
        await m.answer("✅ شماره تلفن شما با موفقیت تأیید شد!", reply_markup=ReplyKeyboardRemove())
    else:
        await m.answer("❌ لطفاً شماره تلفن متعلق به همین حساب کاربری را ارسال کنید.")


@user_router.callback_query(F.data.startswith("cap:"))
async def cap_cb(cb: CallbackQuery, bot: Bot):
    try:
        gid = int(cb.data.split(":")[1])
    except (ValueError, IndexError):
        return await cb.answer("bad")
    g = get_gw(gid)
    if not g or g["status"] != "active":
        return await cb.answer(t(cb.from_user.id, "finished"), show_alert=True)
    with db(write=True) as c:
        c.execute("INSERT OR IGNORE INTO entrants (giveaway_id,user_id,captcha_ok,joined_at) VALUES (?,?,1,?)", (gid, cb.from_user.id, int(time.time())))
        c.execute("UPDATE entrants SET captcha_ok=1 WHERE giveaway_id=? AND user_id=?", (gid, cb.from_user.id))
    text, markup, reply_kb = await entry_screen(bot, gid, cb.from_user)
    try:
        if reply_kb:
            await cb.message.answer(text, reply_markup=reply_kb)
        else:
            await cb.message.edit_text(text, reply_markup=markup)
    except TelegramBadRequest:
        pass
    await cb.answer(t(cb.from_user.id, "captcha_ok"))


@user_router.callback_query(F.data.startswith("chk:"))
async def chk(cb: CallbackQuery, bot: Bot):
    try:
        gid = int(cb.data.split(":")[1])
    except (ValueError, IndexError):
        return await cb.answer("bad")
    text, markup, reply_kb = await entry_screen(bot, gid, cb.from_user)
    try:
        if reply_kb:
            await cb.message.answer(text, reply_markup=reply_kb)
        else:
            await cb.message.edit_text(text, reply_markup=markup)
        await cb.answer()
    except TelegramBadRequest:
        await cb.answer(t(cb.from_user.id, "no_change"))


@user_router.callback_query(F.data.startswith("top:"))
async def top_cb(cb: CallbackQuery):
    try:
        gid = int(cb.data.split(":")[1])
    except (ValueError, IndexError):
        return await cb.answer("bad")
    rows = leaderboard(gid, 10)
    if not rows:
        return await cb.answer("هنوز کسی دعوتی نداشته.", show_alert=True)
    with db() as c:
        lines = ["🏆 <b>برترین دعوت‌کنندگان این قرعه‌کشی</b>\n", "🥇 ────────────────────"]
        for i, r in enumerate(rows, 1):
            u = c.execute("SELECT username, full_name FROM entrants WHERE giveaway_id=? AND user_id=?", (gid, r["inviter_id"])).fetchone()
            if u and u["username"]:
                name = f"@{u['username']}"
            elif u and u["full_name"]:
                name = html.escape(u["full_name"])
            else:
                name = "—"
            lines.append(f"{i}. {name} ← <b>{r['c']} دعوت</b>")
    text = "\n".join(lines)
    try:
        await cb.message.edit_text(text, reply_markup=kb([btn("🔙 بازگشت به کارت شرکت", callback_data=f"chk:{gid}")]))
    except TelegramBadRequest:
        pass
    await cb.answer()


# =====================================================
#                       ادمین
# =====================================================
PANEL_TEXT = "🎛 <b>پنل مدیریت و کنترل پیشرفته قرعه‌کشی‌ها</b>"


def panel_kb():
    return kb(
        [btn("➕ ساخت قرعه‌کشی جدید", callback_data="adm:new")],
        [btn("📋 لیست قرعه‌کشی‌های فعال", callback_data="adm:list")],
        [btn("📝 تنظیمات متون کانال", callback_data="adm:tpl")],
        [btn("📢 همگانی (Broadcast)", callback_data="adm:bc")],
        [btn("📊 آمار و گزارش کل", callback_data="adm:stats")],
    )


BACK_HOME = kb([btn("🔙 بازگشت به پنل", callback_data="adm:home")])
ABORT_KB = kb([btn("❌ انصراف و لغو", callback_data="adm:abort")])


async def show(cb: CallbackQuery, text: str, markup=None):
    try:
        await cb.message.edit_text(text, reply_markup=markup)
    except TelegramBadRequest:
        pass
    await cb.answer()


def gw_info(g) -> str:
    chans = " ، ".join(gw_channels(g["id"])) or "—"
    parts = [
        f"🎁 <b>قرعه‌کشی شماره #{g['id']} · {html.escape(g['title'])}</b>",
        "⚙️ ════════════════════",
        f"🏆 <b>جوایز:</b> {html.escape(g['prizes'])}",
        f"👥 <b>تعداد برنده:</b> {g['winners_count']} نفر",
        f"🖼 <b>بنر:</b> {'دارد' if g['banner_url'] else 'ندارد'}",
        f"📢 <b>کانال‌ها:</b> {chans}",
        f"👫 <b>حداقل دعوت:</b> {g['min_invites']} نفر",
        f"🤖 <b>کپچا:</b> {'روشن' if g['captcha'] else 'خاموش'}",
        f"📱 <b>تأیید شماره:</b> {'روشن' if g['req_phone'] else 'خاموش'}",
        f"📣 <b>اسپانسر:</b> {g['sponsor_text'] or '—'}",
        f"⏰ <b>پایان:</b> {fmt_time(g['ends_at'])}",
        f"📊 <b>ورودی‌ها:</b> کل: {n_entrants(g['id'])} | واجد شرایط: {len(eligible(g['id']))}",
        f"📌 <b>وضعیت:</b> <code>{g['status']}</code>",
    ]
    return "\n".join(parts)


class BroadcastFSM(StatesGroup):
    msg = State()


class ExtendFSM(StatesGroup):
    minutes = State()


class EditTemplateFSM(StatesGroup):
    key = State()
    val = State()


@admin_router.message(Command("panel"))
async def panel_cmd(m: Message, state: FSMContext):
    await state.clear()
    await m.answer(PANEL_TEXT, reply_markup=panel_kb())


@admin_router.callback_query(F.data.startswith("adm:"))
async def adm_cb(cb: CallbackQuery, state: FSMContext, bot: Bot):
    p = cb.data.split(":")
    act = p[1]

    if act == "home":
        await state.clear()
        return await show(cb, PANEL_TEXT, panel_kb())

    if act == "abort":
        await state.clear()
        return await show(cb, "❌ عملیات لغو شد.\n\n" + PANEL_TEXT, panel_kb())

    # --- مدیریت متون کانال ---
    if act == "tpl":
        buttons = []
        for k, label in TEMPLATE_LABELS.items():
            buttons.append([btn(label, callback_data=f"adm:etpl:{k}")])
        buttons.append([btn("🔙 بازگشت به پنل", callback_data="adm:home")])
        return await show(cb, "📝 <b>کدام متن کانال را می‌خواهید ویرایش کنید؟</b>", kb(*buttons))

    if act == "etpl":
        t_key = p[2]
        curr_val = get_template(t_key)
        await state.update_data(edit_t_key=t_key)
        await state.set_state(EditTemplateFSM.val)
        msg = (
            f"📝 <b>ویرایش متن: {TEMPLATE_LABELS.get(t_key, t_key)}</b>\n\n"
            f"<b>متن فعلی:</b>\n<code>{html.escape(curr_val)}</code>\n\n"
            f"👇 لطفاً متن جدید را ارسال کنید:"
        )
        return await show(cb, msg, ABORT_KB)

    if act == "bc":
        await state.set_state(BroadcastFSM.msg)
        return await show(cb, "📢 <b>پیام همگانی خود را ارسال یا ریپلای کنید:</b>", ABORT_KB)

    if act == "new":
        await state.set_state(NewGW.title)
        return await show(cb, "📝 <b>عنوان قرعه‌کشی را وارد کنید:</b>", ABORT_KB)

    if act == "stats":
        with db() as c:
            n_gw = c.execute("SELECT COUNT(*) AS n FROM giveaways").fetchone()["n"]
            n_act = c.execute("SELECT COUNT(*) AS n FROM giveaways WHERE status='active'").fetchone()["n"]
            n_fin = c.execute("SELECT COUNT(*) AS n FROM giveaways WHERE status='finished'").fetchone()["n"]
            n_u = c.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
            n_r = c.execute("SELECT COUNT(*) AS n FROM referrals WHERE verified=1").fetchone()["n"]
        return await show(
            cb,
            f"📊 <b>آمار کلی سیستم</b>\n\n"
            f"🎁 کل قرعه‌کشی‌ها: {n_gw}\n"
            f"🟢 فعال: {n_act}\n"
            f"🔵 به پایان رسیده: {n_fin}\n"
            f"👥 کل کاربران ربات: {n_u}\n"
            f"👫 کل دعوت‌های موفق: {n_r}",
            BACK_HOME)

    if act == "list":
        with db() as c:
            rows = c.execute("SELECT * FROM giveaways WHERE status IN ('active','pending') ORDER BY id DESC").fetchall()
        if not rows:
            return await show(cb, "هیچ قرعه‌کشی فعالی یافت نشد.", BACK_HOME)
        buttons = []
        for r in rows:
            buttons.append([btn(f"#{r['id']} · {r['title']} ({len(eligible(r['id']))} نفر)", callback_data=f"adm:view:{r['id']}")])
        buttons.append([btn("🔙 پنل", callback_data="adm:home")])
        return await show(cb, "📋 <b>لیست قرعه‌کشی‌های فعال</b>", kb(*buttons))

    try:
        gid = int(p[-1])
    except (ValueError, IndexError):
        return await show(cb, "داده نامعتبر.", BACK_HOME)

    g = get_gw(gid)
    if not g:
        return await show(cb, "یافت نشد.", BACK_HOME)

    if act == "view":
        rows = [
            [btn("🎲 اجرا و قرعه‌کشی فوری", callback_data=f"adm:ask:draw:{gid}")],
            [btn("⏰ تمدید زمان پایان", callback_data=f"adm:ext:{gid}")],
            [btn("🗑 لغو کامل قرعه‌کشی", callback_data=f"adm:ask:cancel:{gid}")],
            [btn("🏆 لیدربورد دعوت‌ها", callback_data=f"adm:lb:{gid}")],
            [btn("📥 دانلود خروجی CSV", callback_data=f"adm:csv:{gid}")],
            [btn("🔙 بازگشت به لیست", callback_data="adm:list")],
        ]
        return await show(cb, gw_info(g), kb(*rows))

    if act == "ext":
        await state.update_data(ext_gid=gid)
        await state.set_state(ExtendFSM.minutes)
        return await show(cb, "⏰ <b>چند دقیقه می‌خواهید به زمان پایان اضافه کنید؟</b>", ABORT_KB)

    if act == "lb":
        rows = leaderboard(gid, 15)
        if not rows:
            return await show(cb, "هنوز کسی دعوتی نداشته.", kb([btn("🔙 بازگشت", callback_data=f"adm:view:{gid}")]))
        with db() as c:
            lines = []
            for i, r in enumerate(rows, 1):
                u = c.execute("SELECT username, full_name FROM entrants WHERE giveaway_id=? AND user_id=?", (gid, r["inviter_id"])).fetchone()
                if u and u["username"]:
                    nm = f"@{u['username']}"
                elif u and u["full_name"]:
                    nm = u["full_name"]
                else:
                    nm = "—"
                lines.append(f"{i}. {nm} — {r['c']}")
        return await show(cb, "🏆 <b>لیدربورد دعوت‌کنندگان</b>\n\n" + "\n".join(lines), kb([btn("🔙 بازگشت", callback_data=f"adm:view:{gid}")]))

    if act == "ask":
        if len(p) < 4:
            return await show(cb, "داده نامعتبر.", BACK_HOME)
        what = p[2]
        text = "آیا اطمینان دارید که می‌خواهید قرعه‌کشی انجام شود؟" if what == "draw" else "آیا از لغو این قرعه‌کشی اطمینان دارید؟"
        return await show(cb, text, kb([
            btn("✅ بله، انجام شود", callback_data=f"adm:do:{what}:{gid}"),
            btn("↩️ انصراف", callback_data=f"adm:view:{gid}"),
        ]))

    if act == "do":
        if len(p) < 4:
            return await show(cb, "داده نامعتبر.", BACK_HOME)
        what = p[2]
        if what == "draw":
            spawn(finish_giveaway(bot, gid))
            return await show(cb, "⏳ قرعه‌کشی در حال انجام است...", BACK_HOME)
        await cancel_giveaway(bot, gid)
        return await show(cb, "🚫 قرعه‌کشی لغو گردید.", BACK_HOME)


@admin_router.message(EditTemplateFSM.val)
async def save_template_val(m: Message, state: FSMContext):
    data = await state.get_data()
    t_key = data.get("edit_t_key")
    new_val = m.text or ""

    if not new_val:
        return await m.answer("متن نمی‌تواند خالی باشد.", reply_markup=ABORT_KB)

    set_template(t_key, new_val)
    await state.clear()
    await m.answer(f"✅ متن <b>{TEMPLATE_LABELS.get(t_key, t_key)}</b> با موفقیت به‌روزرسانی شد!", reply_markup=panel_kb())


@admin_router.message(BroadcastFSM.msg)
async def process_broadcast(m: Message, state: FSMContext, bot: Bot):
    await state.clear()
    with db() as c:
        uids = [r["user_id"] for r in c.execute("SELECT user_id FROM users").fetchall()]
    
    count = 0
    for uid in uids:
        try:
            await m.copy_to(chat_id=uid)
            count += 1
            await asyncio.sleep(DM_DELAY)
        except Exception:
            pass
    await m.answer(f"✅ پیام همگانی با موفقیت به {count} کاربر ارسال شد.", reply_markup=panel_kb())


@admin_router.message(ExtendFSM.minutes)
async def process_extend(m: Message, state: FSMContext):
    if not (m.text and m.text.isdigit()):
        return await m.answer("عدد بفرستید.")
    data = await state.get_data()
    gid = data["ext_gid"]
    mins = int(m.text)
    
    with db(write=True) as c:
        c.execute("UPDATE giveaways SET ends_at = ends_at + ? WHERE id=?", (mins * 60, gid))
    await state.clear()
    await m.answer(f"✅ زمان پایان قرعه‌کشی #{gid} به میزان {mins} دقیقه تمدید شد.", reply_markup=panel_kb())


# ---------------- FSM جدید ساخت قرعه‌کشی ----------------
class NewGW(StatesGroup):
    title = State()
    banner = State()
    prizes = State()
    codes = State()
    winners = State()
    start_at = State()
    minutes = State()
    channel = State()
    extra = State()
    invites = State()
    sponsor = State()
    captcha = State()
    phone = State()


async def bot_is_admin(bot: Bot, ch: str) -> bool:
    try:
        me = await bot.me()
        m = await bot.get_chat_member(ch, me.id)
        return getattr(m, "status", None) in ("administrator", "creator")
    except TelegramBadRequest:
        return False
    except Exception as e:
        log.warning("bot_is_admin(%s): %s", ch, e)
        return False


async def safe_answer(m: Message, text: str, **kw):
    try:
        return await m.answer(text, **kw)
    except TelegramBadRequest as e:
        log.warning("safe_answer: %s", e)


@admin_router.message(NewGW.title)
async def s1(m: Message, state: FSMContext):
    title = (m.text or "").strip()
    if not title or len(title) > 200:
        return await safe_answer(m, "عنوان باید ۱ تا ۲۰۰ کاراکتر باشد.", reply_markup=ABORT_KB)
    await state.update_data(title=title)
    await state.set_state(NewGW.banner)
    await safe_answer(m, "🖼 <b>بنر تصویری:</b>\nعکس ارسال کنید، یا لینک مستقیم عکس بفرستید، یا عدد - را برای بدون عکس ارسال کنید:", reply_markup=ABORT_KB)


@admin_router.message(NewGW.banner)
async def s_banner(m: Message, state: FSMContext):
    banner_url = None
    if m.photo:
        banner_url = m.photo[-1].file_id
    elif m.text and m.text.strip() != "-":
        banner_url = m.text.strip()
    
    await state.update_data(banner_url=banner_url)
    await state.set_state(NewGW.prizes)
    await safe_answer(m, "🎁 <b>جوایز را با علامت | جدا کنید:</b>\nمثال: کد اکانت|گوشی|تخفیف", reply_markup=ABORT_KB)


@admin_router.message(NewGW.prizes)
async def s2(m: Message, state: FSMContext):
    prizes = (m.text or "").strip()
    if not prizes:
        return await safe_answer(m, "متن جوایز نامعتبر است.", reply_markup=ABORT_KB)
    await state.update_data(prizes=prizes)
    await state.set_state(NewGW.codes)
    await safe_answer(m, "🔑 <b>کدهای جایزه جهت ارسال خودکار به برندگان (با | جدا کنید):</b>\nاگر ندارد عدد - بفرستید.\nمثال: CODE1|CODE2|CODE3", reply_markup=ABORT_KB)


@admin_router.message(NewGW.codes)
async def s_codes(m: Message, state: FSMContext):
    text = (m.text or "").strip()
    prize_codes = None if text == "-" else text
    await state.update_data(prize_codes=prize_codes)
    await state.set_state(NewGW.winners)
    await safe_answer(m, "👥 <b>تعداد برندگان؟ (عدد بین ۱ تا ۱۰۰):</b>", reply_markup=ABORT_KB)


@admin_router.message(NewGW.winners)
async def s3(m: Message, state: FSMContext):
    if not (m.text and m.text.isdigit() and 0 < int(m.text) <= 100):
        return await safe_answer(m, "عدد بین ۱ تا ۱۰۰ وارد کنید.", reply_markup=ABORT_KB)
    await state.update_data(winners=int(m.text))
    await state.set_state(NewGW.start_at)
    await safe_answer(m, "⏳ <b>زمان شروع ارسال پست (به دقیقه، 0 = ارسال فوری):</b>", reply_markup=ABORT_KB)


@admin_router.message(NewGW.start_at)
async def s4(m: Message, state: FSMContext):
    if not (m.text and m.text.isdigit()):
        return await safe_answer(m, "عدد وارد کنید.", reply_markup=ABORT_KB)
    await state.update_data(start_after=int(m.text))
    await state.set_state(NewGW.minutes)
    await safe_answer(m, "⏰ <b>مدت زمان قرعه‌کشی (به دقیقه):</b>", reply_markup=ABORT_KB)


@admin_router.message(NewGW.minutes)
async def s5(m: Message, state: FSMContext):
    if not (m.text and m.text.isdigit() and 0 < int(m.text) <= 60 * 24 * 90):
        return await safe_answer(m, "عدد معتبر وارد کنید.", reply_markup=ABORT_KB)
    await state.update_data(minutes=int(m.text))
    await state.set_state(NewGW.channel)
    await safe_answer(m, "📢 <b>آیدی کانال پست قرعه‌کشی (مثلاً @MyChannel):</b>", reply_markup=ABORT_KB)


@admin_router.message(NewGW.channel)
async def s6(m: Message, state: FSMContext, bot: Bot):
    ch = (m.text or "").strip().lower()
    if not ch.startswith("@") or len(ch) < 2 or not await bot_is_admin(bot, ch):
        return await safe_answer(m, "ربات در این کانال ادمین نیست یا آیدی نامعتبر است.", reply_markup=ABORT_KB)
    await state.update_data(channel=ch)
    await state.set_state(NewGW.extra)
    await safe_answer(m, "📢 <b>کانال‌های اجباری اضافی (با فاصله یا -):</b>", reply_markup=ABORT_KB)


@admin_router.message(NewGW.extra)
async def s7(m: Message, state: FSMContext, bot: Bot):
    text = (m.text or "").strip()
    extras = []
    if text != "-":
        extras = [x.lower() for x in re.split(r"[\s,،]+", text) if x]
        bad = [x for x in extras if not x.startswith("@") or not await bot_is_admin(bot, x)]
        if bad:
            return await safe_answer(m, "ربات در کانال‌های زیر ادمین نیست:\n" + "\n".join(bad), reply_markup=ABORT_KB)
    await state.update_data(extra=extras)
    await state.set_state(NewGW.invites)
    await safe_answer(m, "👫 <b>حداقل تعداد دعوت لازم (0 = بدون شرط):</b>", reply_markup=ABORT_KB)


@admin_router.message(NewGW.invites)
async def s8(m: Message, state: FSMContext):
    if not (m.text and m.text.isdigit() and int(m.text) <= 1000):
        return await safe_answer(m, "عدد معتبر بفرستید.", reply_markup=ABORT_KB)
    await state.update_data(invites=int(m.text))
    await state.set_state(NewGW.sponsor)
    await safe_answer(m, "📣 <b>اطلاعات اسپانسر «عنوان|لینک» یا -:</b>", reply_markup=ABORT_KB)


@admin_router.message(NewGW.sponsor)
async def s9(m: Message, state: FSMContext):
    text = (m.text or "").strip()
    sp_text = sp_url = None
    if text != "-":
        if "|" not in text:
            return await safe_answer(m, "فرمت: عنوان|لینک", reply_markup=ABORT_KB)
        sp_text, sp_url = [x.strip() for x in text.split("|", 1)]
    await state.update_data(sponsor_text=sp_text, sponsor_url=sp_url)
    await state.set_state(NewGW.captcha)
    await safe_answer(m, "🛡 <b>تأییدیه کپچا فعال باشد؟ (yes/no):</b>", reply_markup=ABORT_KB)


@admin_router.message(NewGW.captcha)
async def s10(m: Message, state: FSMContext):
    v = (m.text or "").strip().lower()
    cap = 1 if v in ("yes", "y", "بله") else 0
    await state.update_data(captcha=cap)
    await state.set_state(NewGW.phone)
    await safe_answer(m, "📱 <b>احراز هویت با شماره تلفن اجباری باشد؟ (yes/no):</b>", reply_markup=ABORT_KB)


@admin_router.message(NewGW.phone)
async def s11(m: Message, state: FSMContext, bot: Bot):
    v = (m.text or "").strip().lower()
    req_phone = 1 if v in ("yes", "y", "بله") else 0

    d = await state.get_data()
    now = int(time.time())
    start_at = now + d["start_after"] * 60
    ends_at = start_at + d["minutes"] * 60
    seed = secrets.token_hex(16)

    chans = list(dict.fromkeys(x.lower() for x in [d["channel"], *d["extra"]]))
    status = "pending" if d["start_after"] > 0 else "active"

    with db(write=True) as c:
        cur = c.execute("""
            INSERT INTO giveaways
            (title, prizes, prize_codes, banner_url, winners_count, post_channel, start_at, ends_at,
             min_invites, sponsor_text, sponsor_url, captcha, req_phone, seed, status,
             created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (d["title"], d["prizes"], d["prize_codes"], d["banner_url"], d["winners"], d["channel"],
              start_at, ends_at, d["invites"], d["sponsor_text"],
              d["sponsor_url"], d["captcha"], req_phone, seed, status, now))
        gid = cur.lastrowid
        c.executemany("INSERT INTO gw_channels VALUES (?,?)", [(gid, x) for x in chans])

    if status == "pending":
        await state.clear()
        return await safe_answer(m, f"✅ قرعه‌کشی #{gid} ثبت شد.", reply_markup=BACK_HOME)

    g = get_gw(gid)
    try:
        sent = await send_post_msg(bot, g["post_channel"], g, 0)
        with db(write=True) as c:
            c.execute("UPDATE giveaways SET message_id=? WHERE id=?", (sent.message_id, gid))
        await safe_answer(m, f"✅ قرعه‌کشی #{gid} منتشر شد.", reply_markup=BACK_HOME)
    except TelegramBadRequest as e:
        await safe_answer(m, f"⚠️ خطای ارسال: {e}", reply_markup=BACK_HOME)

    await state.clear()


# ---------------- اجرا ----------------
async def main():
    if BOT_TOKEN == "PUT_YOUR_TOKEN_HERE":
        raise SystemExit("❌ BOT_TOKEN را تنظیم کن.")
    if not ADMIN_IDS or ADMIN_IDS == {0}:
        raise SystemExit("❌ ADMIN_IDS را تنظیم کن.")

    init_db()
    log.info("DB ready: %s", DB_PATH)

    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(admin_router)
    dp.include_router(user_router)

    spawn(watcher(bot))
    log.info("Bot started. Admins: %s", ADMIN_IDS)

    try:
        await dp.start_polling(bot)
    finally:
        log.info("Shutting down...")
        for task in list(BG_TASKS):
            task.cancel()
        await asyncio.gather(*BG_TASKS, return_exceptions=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
