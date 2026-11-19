#CREDIT - @DG_DRIFT 
#MAIN CHANNEL - @DGDRIFT #
import os
import sys
import time
import json
import zipfile
import subprocess
import threading
import psutil
from datetime import datetime
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

# ================= BOT CONFIG =================
BOT_TOKEN = "9271969557:AAF_iPW_zSRErg3guLI-2VV89PRFNpa-jaE"          # <-- Replace with your bot token
OWNER_ID = 7482700557                 # <-- Replace with your Telegram user ID

STORAGE_DIR = "user_files"
UPLOAD_DIR = os.path.join(STORAGE_DIR, "uplo556ads")
DATA_FILE = os.path.join(STORAGE_DIR, "users.json")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(STORAGE_DIR, exist_ok=True)

if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, 'w') as f:
        pass

# ================= GLOBALS =================
users = {}                 # user_id -> {"files": [list_of_filenames]}
active_scripts = {}        # user_id -> file_path -> process
logs_store = {}            # user_id -> file_path -> logs (internal only)
install_waiting_users = {}
bot_start_time = time.time()
START_TIME = datetime.now()

RECOMMENDED_PACKAGES = [
    "pip", "setuptools", "wheel", "requests", "numpy", "pandas", "flask", "aiohttp",
    "pyrogram", "python-dotenv", "beautifulsoup4", "lxml", "pillow", "matplotlib",
    "scipy", "scikit-learn", "pytest"
]
PYTG_CALLS_PACKAGE = "git+https://github.com/pytgcalls/pytgcalls.git"

# ================= DATA PERSISTENCE =================
def save_data():
    temp_file = DATA_FILE + ".tmp"
    with open(temp_file, "w") as f:
        json.dump(users, f, indent=4)
    os.replace(temp_file, DATA_FILE)

def load_data():
    global users
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                raw_data = json.load(f)
                users.clear()
                for k, v in raw_data.items():
                    users[int(k)] = v
        except Exception as e:
            print(f"Load Error: {e}")
            users = {}

load_data()

# ================= UTILITIES =================
def uptime():
    s = int(time.time() - bot_start_time)
    return f"{s//3600}h {(s%3600)//60}m {s%60}s"

def user_folder(uid):
    path = os.path.join(UPLOAD_DIR, str(uid))
    os.makedirs(path, exist_ok=True)
    return path

def get_system_info():
    cpu_freq = psutil.cpu_freq()
    cpu_ghz = cpu_freq.current / 1000 if cpu_freq else 0.0
    ram = psutil.virtual_memory()
    total_ram_gb = ram.total / (1024 ** 3)
    free_ram_gb = ram.available / (1024 ** 3)
    return cpu_ghz, total_ram_gb, free_ram_gb

def install_requirements(folder):
    req_file = os.path.join(folder, "requirements.txt")
    if os.path.exists(req_file):
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", req_file])
        except:
            pass

# ================= SCRIPT RUNNING & LOGGING =================
def run_script_thread(user_id, file_path):
    try:
        proc = subprocess.Popen(
            [sys.executable, os.path.abspath(file_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        active_scripts.setdefault(user_id, {})[file_path] = proc
        logs_store.setdefault(user_id, {})[file_path] = []

        while True:
            line = proc.stdout.readline()
            if not line and proc.poll() is not None:
                break
            if line:
                logs_store[user_id][file_path].append(line.strip())
                logs_store[user_id][file_path] = logs_store[user_id][file_path][-50:]
        proc.wait()
    except Exception as e:
        print(f"Error in script {file_path}: {e}")
    finally:
        if user_id in active_scripts:
            active_scripts[user_id].pop(file_path, None)

def start_script(user_id, file_path):
    thread = threading.Thread(target=run_script_thread, args=(user_id, file_path), daemon=True)
    thread.start()

# ================= INSTALLATION HELPERS =================
def live_install(cmd_list, chat_id, message_id, description):
    try:
        proc = subprocess.Popen(
            cmd_list,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        output_lines = []
        while True:
            line = proc.stdout.readline()
            if line:
                output_lines.append(line.rstrip())
                if len(output_lines) > 8:
                    output_lines = output_lines[-8:]
                live_text = "\n".join(output_lines)
                try:
                    bot.edit_message_text(
                        f"📥 {description}...\n```\n{live_text}\n```",
                        chat_id=chat_id,
                        message_id=message_id,
                        parse_mode="Markdown"
                    )
                except:
                    pass
            if not line and proc.poll() is not None:
                break
        full_output = "\n".join(output_lines[-4000:])
        if proc.returncode == 0:
            bot.edit_message_text(
                f"✅ {description} installed!\n\n```\n{full_output}\n```",
                chat_id=chat_id,
                message_id=message_id,
                parse_mode="Markdown"
            )
        else:
            bot.edit_message_text(
                f"❌ Failed\n\nError:\n```\n{full_output}\n```",
                chat_id=chat_id,
                message_id=message_id,
                parse_mode="Markdown"
            )
    except Exception as e:
        bot.edit_message_text(
            f"❌ Exception: {str(e)}",
            chat_id=chat_id,
            message_id=message_id
        )

def install_recommended_packages(chat_id, message_id):
    for idx, pkg in enumerate(RECOMMENDED_PACKAGES, start=1):
        live_install(
            ["pip", "install", pkg],
            chat_id,
            message_id,
            f"{pkg} ({idx}/{len(RECOMMENDED_PACKAGES)})"
        )
    live_install(
        ["pip", "install", "--no-deps", PYTG_CALLS_PACKAGE],
        chat_id,
        message_id,
        "pytgcalls (GitHub)"
    )

# ================= TELEGRAM BOT INIT =================
bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None)

# ===== MAIN MENU =====
def control_buttons():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("🌏 Upload"), KeyboardButton("📁 𝐌𝐲 𝐅𝐢𝐥𝐞𝐬")],
            [KeyboardButton("🔄 𝐑𝐞𝐬𝐭𝐚𝐫𝐭"), KeyboardButton("⏹ 𝐒𝐭𝐨𝐩")],
            [KeyboardButton("⚡ 𝐒𝐩𝐞𝐞𝐝"), KeyboardButton("🚀 𝐒𝐭𝐚𝐭𝐮𝐬")],
            [KeyboardButton("⚙️ Recommended Install")]
        ],
        resize_keyboard=True
    )

# ================= COMMAND /start =================
@bot.message_handler(commands=['start'])
def start_command(message):
    uid = message.from_user.id
    if uid not in users:
        users[uid] = {"files": []}
        save_data()

    welcome = (
        "┏━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
        "┃   🚀 DRIFT HOSTING      ┃\n"
        "┃      VERSION 0.3        ┃\n"
        "┗━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
        f"👤 Wᴇʟᴄᴏᴍᴇ {message.from_user.first_name}!\n"
        f"🆔 Uꜱᴇʀ ID: {uid}\n\n"
        f"📁 Fɪʟᴇꜱ: {len(users[uid]['files'])}\n\n"
        "⚡ Fᴇᴀᴛᴜʀᴇꜱ:\n"
        "• Aᴜᴛᴏ-Rᴇᴄᴏᴠᴇʀʏ Sʏꜱᴛᴇᴍ\n"
        "• Pʏᴛʜᴏɴ / Jꜱ / Zɪᴘ Sᴜᴘᴘᴏʀᴛ\n\n"
        "Uꜱᴇ ᴛʜᴇ Bᴜᴛᴛᴏɴꜱ Bᴇʟᴏᴡ Tᴏ Nᴀᴠɪɢᴀᴛᴇ."
    )
    bot.send_message(uid, welcome, reply_markup=control_buttons())

# ================= TEXT HANDLER =================
@bot.message_handler(func=lambda m: True, content_types=['text'])
def text_handler(message):
    uid = message.from_user.id
    text = message.text
    user_data = users.setdefault(uid, {"files": []})

    if text.startswith("🌏"):
        bot.reply_to(message, "📤 𝐒𝐞𝐧𝐝 𝐲𝐨𝐮𝐫 .𝐩𝐲, .𝐳𝐢𝐩, .𝐭𝐱𝐭 𝐟𝐢𝐥𝐞 𝐧𝐨𝐰.")

    elif text.startswith("⚙️ Recommended Install"):
        bot.reply_to(
            message,
            "📦 ```Install Python Package\n"
            "Send me the package name to install.\n"
            "Examples:\n"
            "• requests\n"
            "• numpy\n"
            "• pandas==1.5.0\n"
            "• git+https://github.com/user/repo.git\n"
            "Or send a requirements.txt file.\n"
            "Recommended packages:\n" + ", ".join(RECOMMENDED_PACKAGES) +
            "\n\nSend ✅ to start installation or type a package name to install it manually.```",
            parse_mode="Markdown"
        )
        install_waiting_users[uid] = True

    elif install_waiting_users.get(uid):
        install_waiting_users[uid] = False
        if text.strip() == "✅":
            msg = bot.reply_to(message, "📥 Starting installation...")
            thread = threading.Thread(
                target=install_recommended_packages,
                args=(message.chat.id, msg.message_id),
                daemon=True
            )
            thread.start()
        else:
            msg = bot.reply_to(message, f"📥 Installing {text.strip()}...")
            thread = threading.Thread(
                target=live_install,
                args=(["pip", "install", text.strip()], message.chat.id, msg.message_id, text.strip()),
                daemon=True
            )
            thread.start()

    elif text.startswith("📁"):
        files = user_data["files"]
        if not files:
            bot.reply_to(message, "❌ No files.")
            return
        buttons = [[InlineKeyboardButton(f"{f}", callback_data=f"file_{f}")] for f in files]
        bot.reply_to(message, "📁 𝐘𝐨𝐮𝐫 𝐅𝐢𝐥𝐞𝐬:", reply_markup=InlineKeyboardMarkup(buttons))

    elif text.startswith("⚡"):
        start_time = time.time()
        time.sleep(0.1)
        processing_time = time.time() - start_time
        cpu_ghz, total_ram_gb, free_ram_gb = get_system_info()
        bot.reply_to(
            message,
            f"⚡ 𝗕𝗢𝗧 𝗦𝗣𝗘𝗘𝗗: {round(processing_time, 4)} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀\n\n"
            f"⚙️ 𝗖𝗣𝗨: {round(cpu_ghz, 2)}𝗚𝗛𝘇\n"
            f"💾 𝗥𝗔𝗠: {round(total_ram_gb, 2)}𝗚𝗕\n"
            f"🟢 𝗙𝗥𝗘𝗘: {round(free_ram_gb, 2)}𝗚𝗕"
        )

    elif text.startswith("🔄"):
        # User restart: stop all their scripts, then restart all .py files
        if uid in active_scripts:
            for p in active_scripts[uid].values():
                p.kill()
            active_scripts[uid] = {}
        folder = user_folder(uid)
        for fname in user_data["files"]:
            if fname.endswith(".py"):
                path = os.path.join(folder, fname)
                if os.path.exists(path):
                    start_script(uid, path)
        bot.reply_to(message, "🔄 All your scripts have been restarted.")

    elif text.startswith("⏹"):
        if uid in active_scripts:
            for p in active_scripts[uid].values():
                p.kill()
            active_scripts[uid] = {}
        bot.reply_to(message, "⏹ Stopped all your scripts.")

    elif text.startswith("🚀"):
        total_users = len(users)
        total_files = sum(len(u.get("files", [])) for u in users.values() if u)
        running_scripts = sum(len(active_scripts.get(uid, {})) for uid in users if users.get(uid))
        recovery_saved = total_files
        bot_status = "🟢 𝐔𝐧𝐥𝐨𝐜𝐤𝐞𝐝"
        uptime_seconds = (datetime.now() - START_TIME).total_seconds()
        hours, remainder = divmod(int(uptime_seconds), 3600)
        minutes, seconds = divmod(remainder, 60)
        uptime_str = f"{hours}h {minutes}m {seconds}s"

        bot.reply_to(
            message,
            f"""📊 LIVE STATISTICS

👥 𝐓𝐨𝐭𝐚𝐥 𝐔𝐬𝐞𝐫𝐬: {total_users}
📁 𝐓𝐨𝐭𝐚𝐥 𝐅𝐢𝐥𝐞𝐬: {total_files}
🟢 𝐑𝐮𝐧𝐧𝐢𝐧𝐠 𝐒𝐜𝐫𝐢𝐩𝐭𝐬: {running_scripts}
💾 𝐑𝐞𝐜𝐨𝐯𝐞𝐫𝐲 𝐒𝐚𝐯𝐞𝐝: {recovery_saved}
🔒 𝐁𝐨𝐭 𝐒𝐭𝐚𝐭𝐮𝐬: {bot_status}

⏱️ 𝐔𝐩𝐭𝐢𝐦𝐞: {uptime_str}"""
        )

# ================= FILE HANDLER =================
@bot.message_handler(content_types=['document'])
def document_handler(message):
    uid = message.from_user.id
    user_data = users.setdefault(uid, {"files": []})
    # Limit: 2 files for non-owner, unlimited for owner
    if uid != OWNER_ID and len(user_data["files"]) >= 2:
        bot.reply_to(message, "❌ You have reached the limit of 2 files. Contact the owner for more.")
        return

    doc = message.document
    filename = doc.file_name
    if not filename.endswith((".py", ".zip", ".txt")):
        bot.reply_to(message, "❌ Only .py, .zip, .txt allowed.")
        return

    folder = user_folder(uid)
    save_path = os.path.join(folder, filename)
    msg = bot.reply_to(message, "⬇ Downloading...")

    file_info = bot.get_file(doc.file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    with open(save_path, 'wb') as f:
        f.write(downloaded_file)

    if filename not in user_data["files"]:
        user_data["files"].append(filename)
        save_data()

    if filename.endswith(".zip"):
        with zipfile.ZipFile(save_path, 'r') as zip_ref:
            zip_ref.extractall(folder)
        install_requirements(folder)
        bot.edit_message_text("📦 ZIP extracted.", chat_id=message.chat.id, message_id=msg.message_id)
    elif filename.endswith(".txt"):
        install_requirements(folder)
        bot.edit_message_text("📦 Requirements installed.", chat_id=message.chat.id, message_id=msg.message_id)
    elif filename.endswith(".py"):
        start_script(uid, save_path)
        bot.edit_message_text(f"⚡ Starting {filename}...", chat_id=message.chat.id, message_id=msg.message_id)

# ================= CALLBACK HANDLER =================
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    uid = call.from_user.id
    user_data = users.get(uid, {"files": []})
    data = call.data

    if data.startswith("file_"):
        filename = data[5:]
        user_name = call.from_user.first_name or "User"
        msg = (
            f"⚡ <b>𝐀𝐜𝐭𝐢𝐨𝐧𝐬 𝐟𝐨𝐫</b><code> {filename}</code>\n\n"
            f"🆔 <b>𝐔𝐬𝐞𝐫 𝐈𝐃:</b> <code>{uid}</code>\n"
            f"👤 <b>𝐍𝐚𝐦𝐞:</b><code> {user_name}</code>\n"
            f"🟢 <b>𝐑𝐮𝐧𝐧𝐢𝐧𝐠:</b> <code> 1</code>"
        )
        buttons = [
            [InlineKeyboardButton("▶ Run", callback_data=f"run_{filename}"),
             InlineKeyboardButton("⏹ Stop", callback_data=f"stop_{filename}")],
            [InlineKeyboardButton("⬅ Back", callback_data="myfiles")]
        ]
        bot.edit_message_text(
            msg,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode="HTML"
        )

    elif data == "myfiles":
        files = user_data["files"]
        if not files:
            bot.edit_message_text("❌ No files.", chat_id=call.message.chat.id, message_id=call.message.message_id)
            return
        buttons = [[InlineKeyboardButton(f"{f}", callback_data=f"file_{f}")] for f in files]
        bot.edit_message_text(
            "📁 𝐘𝐨𝐮𝐫 𝐅𝐢𝐥𝐞𝐬:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif data.startswith("run_"):
        fname = data[4:]
        path = os.path.join(user_folder(uid), fname)
        if os.path.exists(path):
            start_script(uid, path)
            bot.answer_callback_query(call.id, f"▶ {fname} started")
        else:
            bot.answer_callback_query(call.id, "❌ File not found")

    elif data.startswith("stop_"):
        fname = data[5:]
        path = os.path.join(user_folder(uid), fname)
        proc = active_scripts.get(uid, {}).get(path)
        if proc:
            proc.kill()
            active_scripts[uid].pop(path, None)
            bot.answer_callback_query(call.id, f"⏹ {fname} stopped")
        else:
            bot.answer_callback_query(call.id, "❌ Script not running")

# ================= AUTO-RESTORE ON START =================
def restore_all():
    load_data()
    print("🔄 Restoring scripts...")
    for uid, data in users.items():
        folder = user_folder(uid)
        for f in data.get("files", []):
            if f.endswith(".py"):
                path = os.path.join(folder, f)
                if os.path.exists(path):
                    start_script(uid, path)
    print("✅ System Ready")

# ================= POLLING =================
if __name__ == "__main__":
    restore_all()
    print("DRIFT HOSTING BoT IS RUNNING 🏃")
    bot.polling(none_stop=True)
