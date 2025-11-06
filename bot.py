import json
import datetime
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# --- Load config & members ---
def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

CONFIG = load_json('config.json')
MEMBERS = load_json('members.json')
PROXIES = CONFIG.get('proxy', None)
GF = CONFIG['google_form']

# --- Helper ---
def get_member(emp_id):
    for m in MEMBERS:
        if m["id"].lower() == emp_id.lower():
            return m
    return None

def get_note_by_date(date_str):
    date = datetime.datetime.strptime(date_str, "%Y-%m-%d")
    if date.weekday() < 5:
        return "Ngày thường (T2-T6)"
    return "Ngày nghỉ (T7, CN) & ngày lễ"

# --- Commands ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = "👋 Xin chào!\nDùng các lệnh sau:\n" \
          "/members - Danh sách thành viên\n" \
          "/register <Mã nhân viên> - Đăng ký upcode"
    await update.message.reply_text(msg)

async def members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "\n".join([f"{m['id']} - {m['name']}" for m in MEMBERS])
    await update.message.reply_text(f"📋 Danh sách thành viên:\n{text}")

async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) == 0:
        await update.message.reply_text("❗ Dùng cú pháp: /register <Mã nhân viên>")
        return

    emp_id = context.args[0]
    member = get_member(emp_id)
    if not member:
        await update.message.reply_text("❌ Không tìm thấy mã nhân viên.")
        return

    today = datetime.date.today().isoformat()
    note = get_note_by_date(today)
    content = f"Nghiệm thu công việc"

    # Lưu tạm dữ liệu đăng ký vào callback_data
    data = json.dumps({
        "id": emp_id,
        "date": today,
        "note": note,
        "content": content
    })
    kb = [[InlineKeyboardButton("✅ Submit", callback_data=f"submit|{data}")]]
    markup = InlineKeyboardMarkup(kb)
    msg = (f"🧾 Đăng ký upcode cho *{member['name']}*\n"
           f"Ngày: {today}\n"
           f"Nội dung: {content}\n"
           f"Ghi chú: {note}")
    await update.message.reply_text(msg, parse_mode="MarkdownV2", reply_markup=markup)
    

# --- Handle Submit ---
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not query.data.startswith("submit|"):
        return

    data = json.loads(query.data.split("|", 1)[1])
    member = get_member(data["id"])
    if not member:
        await query.edit_message_text("⚠️ Thành viên không tồn tại.")
        return

    # Build form payload
    mapping = GF["mapping"]
    form_data = {
        mapping["employee_id"]: member["id"],
        mapping["name"]: member["name"],
        mapping["email"]: member["email"],
        mapping["center"]: member["center"],
        mapping["dept"]: member["dept"],
        mapping["doituong"]: member["doituong"],
        mapping["work_mode"]: member["work_mode"],
        mapping["phone"]: member["phone"],
        mapping["noi_dung"]: data["content"],
        mapping["ngay_thuc_hien"]: data["date"],
        mapping["ghi_chu"]: data["note"]
    }

    try:
        r = requests.post(GF["action_url"], data=form_data, proxies=PROXIES, timeout=15)
        if r.status_code in (200, 302):
            await query.edit_message_text(f"✅ Đăng ký thành công cho {member['name']} ngày {data['date']}")
        else:
            await query.edit_message_text(f"❌ Lỗi submit (mã {r.status_code})")
    except Exception as e:
        await query.edit_message_text(f"⚠️ Lỗi gửi form: {e}")

# --- Main entry ---
def main():
    token = CONFIG["telegram_token"]
    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("members", members))
    app.add_handler(CommandHandler("register", register))
    app.add_handler(CallbackQueryHandler(button))
    app.run_polling()

if __name__ == "__main__":
    main()

