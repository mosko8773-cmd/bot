import os
import secrets
import string
import logging
from datetime import datetime, timedelta, timezone

import firebase_admin
from firebase_admin import credentials, db

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# ================ CONFIG ================

BOT_TOKEN = os.getenv("BOT_TOKEN", "9063352443:AAF3n51yrdv-GkVb5t5Ftvdj9FBcjVzHTkk")
DATABASE_URL = "https://mosko-wire-default-rtdb.firebaseio.com"
SERVICE_ACCOUNT = "serviceAccountKey.json"
CHANNEL = "https://t.me/MOSKOCHEATS"

DAILY_POINTS = 2
KEY_PRICE = 6
REFERRAL_POINTS = 2

logging.basicConfig(level=logging.INFO)

if not firebase_admin._apps:
    cred = credentials.Certificate(SERVICE_ACCOUNT)
    firebase_admin.initialize_app(
        cred, {"databaseURL": DATABASE_URL}
    )

# ================ LANGUAGES ================

TEXT = {
    "ar": {
        "welcome": "🚀 أهلاً بك في MOSKO CHEATS",
        "balance": "💰 رصيدك: {points} نقطة",
        "daily": "🎁 الهدية اليومية",
        "buy": "🔑 شراء مفتاح",
        "money": "💰 رصيدي",
        "ref": "👥 نظام الإحالة",
        "language": "🌐 تغيير اللغة",
        "channel": "📢 القناة الرسمية",
        "daily_ok": "🎁 حصلت على نقطتين!",
        "daily_no": "⏳ استلمت هديتك اليومية بالفعل!",
        "insufficient": "❌ نقاطك غير كافية! تحتاج 6 نقاط.",
        "key_ok": "✅ تم إنشاء مفتاحك بنجاح!\n\n🔑 المفتاح:\n{key}\n\n⏳ الصلاحية: 24 ساعة\n📅 الانتهاء: {expires}\n💰 رصيدك: {points}",
        "ref_title": "👥 نظام الإحالة",
        "ref_desc": "ادع أصدقاءك واحصل على نقطتين لكل مستخدم جديد!",
        "ref_count": "عدد إحالاتك: {count}",
        "ref_link": "🔗 رابط دعوتك:\n{link}",
        "lang_changed": "✅ تم تغيير اللغة بنجاح!",
        "language_choose": "🌐 اختر لغتك / Choose your language",
        "help": "استخدم الأزرار للتحكم في البوت.",
        "price": "🔑 سعر مفتاح اليوم الواحد: 6 نقاط",
    },
    "en": {
        "welcome": "🚀 Welcome to MOSKO CHEATS",
        "balance": "💰 Your balance: {points} points",
        "daily": "🎁 Daily Reward",
        "buy": "🔑 Buy Key",
        "money": "💰 My Balance",
        "ref": "👥 Referral System",
        "language": "🌐 Change Language",
        "channel": "📢 Official Channel",
        "daily_ok": "🎁 You received 2 points!",
        "daily_no": "⏳ You already claimed today's reward!",
        "insufficient": "❌ Not enough points! You need 6 points.",
        "key_ok": "✅ Your key was generated!\n\n🔑 Key:\n{key}\n\n⏳ Validity: 24 hours\n📅 Expires: {expires}\n💰 Balance: {points}",
        "ref_title": "👥 Referral System",
        "ref_desc": "Invite friends and earn 2 points for every new user!",
        "ref_count": "Your referrals: {count}",
        "ref_link": "🔗 Your referral link:\n{link}",
        "lang_changed": "✅ Language changed successfully!",
        "language_choose": "🌐 Choose your language / اختر لغتك",
        "help": "Use the buttons to control the bot.",
        "price": "🔑 One-day key price: 6 points",
    }
}


def tr(uid, key, **kwargs):
    user = db.reference(f"users/{uid}").get() or {}
    lang = user.get("language", "ar")
    return TEXT.get(lang, TEXT["ar"])[key].format(**kwargs)


def now():
    return datetime.now(timezone.utc)


def user_ref(uid):
    return db.reference(f"users/{uid}")


def get_user(uid):
    return user_ref(uid).get() or {}


def language_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🇩🇿 العربية", callback_data="lang_ar"),
            InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")
        ]
    ])


def main_keyboard(uid):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(tr(uid, "daily"), callback_data="daily"),
            InlineKeyboardButton(tr(uid, "buy"), callback_data="buy")
        ],
        [
            InlineKeyboardButton(tr(uid, "money"), callback_data="balance"),
            InlineKeyboardButton(tr(uid, "ref"), callback_data="ref")
        ],
        [
            InlineKeyboardButton(tr(uid, "language"), callback_data="language")
        ],
        [
            InlineKeyboardButton(
                tr(uid, "channel"),
                url=CHANNEL
            )
        ]
    ])


# ================ USER SYSTEM ================

def create_user(uid, username, first_name):
    created = {"new": False}

    def transaction(user):
        if user is None:
            created["new"] = True
            return {
                "points": 0,
                "username": username or "",
                "firstName": first_name or "",
                "language": None,
                "lastDaily": "",
                "referrals": 0,
                "createdAt": now().isoformat()
            }
        return user

    user_ref(uid).transaction(transaction)
    return created["new"]


def daily_reward(uid):
    today = now().date().isoformat()
    result = {"claimed": False}

    def transaction(user):
        if user is None:
            return user

        if user.get("lastDaily") == today:
            return user

        user["points"] = int(user.get("points", 0)) + DAILY_POINTS
        user["lastDaily"] = today
        result["claimed"] = True
        return user

    user_ref(uid).transaction(transaction)
    return result["claimed"]


def add_points(uid, amount):
    def transaction(user):
        if user:
            user["points"] = int(user.get("points", 0)) + amount
        return user

    user_ref(uid).transaction(transaction)


def generate_key():
    chars = string.ascii_uppercase + string.digits
    raw = "".join(secrets.choice(chars) for _ in range(20))
    return "-".join(raw[i:i+5] for i in range(0, 20, 5))


def buy_key(uid):
    result = {"success": False}

    def transaction(user):
        if not user:
            return user

        points = int(user.get("points", 0))

        if points < KEY_PRICE:
            return user

        user["points"] = points - KEY_PRICE
        result["success"] = True
        return user

    user_ref(uid).transaction(transaction)

    if not result["success"]:
        return None

    key = generate_key()
    created = now()
    expires = created + timedelta(hours=24)

    try:
        db.reference("generatedKeys/" + key).set({
            "key": key,
            "telegramId": uid,
            "durationDays": 1,
            "status": "active",
            "createdAt": created.isoformat(),
            "expiresAt": expires.isoformat()
        })
    except Exception:
        add_points(uid, KEY_PRICE)
        raise

    return key, expires


# ================ START ================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg = update.effective_user
    uid = str(tg.id)

    is_new = create_user(uid, tg.username, tg.first_name)

    # Referral: reward only a new user, and never self-referral.
    if is_new and context.args:
        payload = context.args[0]

        if payload.startswith("ref_"):
            inviter = payload[4:]

            if inviter.isdigit() and inviter != uid:
                inviter_data = get_user(inviter)

                if inviter_data:
                    add_points(inviter, REFERRAL_POINTS)

                    def count_referrals(user):
                        if user:
                            user["referrals"] = int(user.get("referrals", 0)) + 1
                        return user

                    user_ref(inviter).transaction(count_referrals)
                    user_ref(uid).update({"referredBy": inviter})

    user = get_user(uid)

    if not user.get("language"):
        await update.message.reply_text(
            "🌐 اختر لغتك / Choose your language",
            reply_markup=language_keyboard()
        )
        return

    claimed = daily_reward(uid)
    user = get_user(uid)

    message = (
        tr(uid, "welcome") + "\n\n" +
        tr(uid, "balance", points=user.get("points", 0)) + "\n"
    )

    if claimed:
        message += "\n" + tr(uid, "daily_ok")

    message += "\n\n" + tr(uid, "price")

    await update.message.reply_text(
        message,
        reply_markup=main_keyboard(uid)
    )


# ================ BUTTONS ================

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    uid = str(query.from_user.id)
    data = query.data

    if data == "language":
        await query.edit_message_text(
            "🌐 Choose your language / اختر لغتك",
            reply_markup=language_keyboard()
        )
        return

    if data in ("lang_ar", "lang_en"):
        lang = data.split("_")[1]
        user_ref(uid).update({"language": lang})

        await query.edit_message_text(
            tr(uid, "lang_changed"),
            reply_markup=main_keyboard(uid)
        )
        return

    user = get_user(uid)

    if data == "daily":
        claimed = daily_reward(uid)

        if claimed:
            message = tr(uid, "daily_ok")
        else:
            message = tr(uid, "daily_no")

        message += "\n\n" + tr(
            uid, "balance",
            points=get_user(uid).get("points", 0)
        )

    elif data == "balance":
        user = get_user(uid)

        message = (
            tr(uid, "balance", points=user.get("points", 0)) +
            "\n" +
            tr(uid, "ref_count", count=user.get("referrals", 0))
        )

    elif data == "buy":
        result = buy_key(uid)

        if not result:
            message = tr(uid, "insufficient")
        else:
            key, expires = result

            message = tr(
                uid,
                "key_ok",
                key=key,
                expires=expires.strftime("%Y-%m-%d %H:%M UTC"),
                points=get_user(uid).get("points", 0)
            )

    elif data == "ref":
        me = await context.bot.get_me()
        link = f"https://t.me/{me.username}?start=ref_{uid}"
        user = get_user(uid)

        message = (
            tr(uid, "ref_title") + "\n\n" +
            tr(uid, "ref_desc") + "\n" +
            tr(uid, "ref_count", count=user.get("referrals", 0)) +
            "\n\n" +
            tr(uid, "ref_link", link=link)
        )

    else:
        return

    await query.edit_message_text(
        message,
        reply_markup=main_keyboard(uid)
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)

    await update.message.reply_text(
        tr(uid, "help"),
        reply_markup=main_keyboard(uid)
    )


# ================ MAIN ================

def main():
    if not BOT_TOKEN or BOT_TOKEN == "PUT_YOUR_BOT_TOKEN_HERE":
        raise ValueError("Set BOT_TOKEN first!")

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(buttons))

    print("MOSKO CHEATS BOT RUNNING...")
    app.run_polling()


if __name__ == "__main__":
    main()
