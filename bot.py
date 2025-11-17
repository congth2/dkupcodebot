import json
import datetime
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)
import requests

# ==== Đọc cấu hình ====
with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

BOT_TOKEN = config["telegram_token"]
FORM_URL = config["google_form_url"]
GF = config['google_form']

# ==== Load danh sách thành viên ====
def load_members():
    with open("members.json", "r", encoding="utf-8") as f:
        return json.load(f)

def save_members(members):
    with open("members.json", "w", encoding="utf-8") as f:
        json.dump(members, f, ensure_ascii=False, indent=2)

# ==== Hàm hỗ trợ ====
def calc_note(date_str):
    date = datetime.datetime.strptime(date_str, "%Y-%m-%d")
    weekday = date.weekday()  # 0=Mon, 6=Sun
    if weekday >= 5:
        return "Ngày nghỉ (T7, CN) & ngày lễ"
    return "Ngày thường (T2–T6)"

# ==== MENU ====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📋 Danh sách thành viên", callback_data="list_members")],
        [InlineKeyboardButton("➕ Thêm thành viên", callback_data="add_member")],
        [InlineKeyboardButton("➖ Xóa thành viên", callback_data="del_member")],
        [InlineKeyboardButton("🧾 Đăng ký upcode", callback_data="register")],
    ]
    await update.message.reply_text("Chọn tính năng:", reply_markup=InlineKeyboardMarkup(keyboard))

# ==== Xử lý menu ====
async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "list_members":
        members = load_members()
        text = "👥 Danh sách thành viên:\n"
        for m in members:
            text += f"- {m['id']} | {m['name']} | {m['email']}\n"
        await query.edit_message_text(text)
    elif data == "add_member":
        await query.edit_message_text("Gửi thông tin dạng:\n`<MãNV>;<HọTên>;<Email>;<ĐT>;<Đơn vị TT>;<Phòng ban>;<Đối tượng>`")
        context.user_data["action"] = "add_member"
    elif data == "del_member":
        await query.edit_message_text("Nhập mã nhân viên cần xoá:")
        context.user_data["action"] = "del_member"
    elif data == "register":
        await query.edit_message_text("Nhập mã nhân viên để đăng ký upcode:")
        context.user_data["action"] = "register"

# ==== Nhận text nhập vào ====
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    action = context.user_data.get("action")
    text = update.message.text.strip()
    members = load_members()

    # Thêm member
    if action == "add_member":
        try:
            parts = text.split(";")
            new_m = {
                "id": parts[0],
                "name": parts[1],
                "email": parts[2],
                "phone": parts[3],
                "center": parts[4],
                "department": parts[5],
                "doituong": parts[6]
            }
            members.append(new_m)
            save_members(members)
            await update.message.reply_text("✅ Thêm thành viên thành công!")
        except Exception as e:
            await update.message.reply_text(f"Lỗi định dạng: {e}")

    # Xoá member
    elif action == "del_member":
        before = len(members)
        members = [m for m in members if m["id"] != text]
        if len(members) < before:
            save_members(members)
            await update.message.reply_text("🗑️ Đã xoá thành viên.")
        else:
            await update.message.reply_text("⚠️ Không tìm thấy mã nhân viên đó.")

    # Đăng ký upcode
    elif action == "register":
        mem = next((m for m in members if m["id"] == text), None)
        if not mem:
            await update.message.reply_text("⚠️ Không tìm thấy mã nhân viên.")
            return

        context.user_data["register_member"] = mem
        await update.message.reply_text("Nhập ngày thực hiện (yyyy-mm-dd), hoặc để trống:")
        context.user_data["action"] = "register_date"

    # Nhập ngày thực hiện
    elif action == "register_date":
        date_str = text if text else datetime.date.today().strftime("%Y-%m-%d")
        context.user_data["date"] = date_str
        default_work = f"Nghiệm thu các nội dung upcode ngày {date_str}"
        await update.message.reply_text(f"Nhập nội dung công việc (mặc định: {default_work}):")
        context.user_data["action"] = "register_task"

    # Nhập nội dung công việc
    elif action == "register_task":
        member = context.user_data["register_member"]
        date_str = context.user_data["date"]
        task = text if text else f"Nghiệm thu các nội dung upcode ngày {date_str}"
        note = calc_note(date_str)

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
            mapping["noi_dung"]: task,
            mapping["ngay_thuc_hien"]: date_str,
            mapping["ghi_chu"]: note
        }

        # Gửi form Google (submit dạng POST)
        resp = requests.post(FORM_URL, data=form_data)
        if resp.status_code == 200:
            await update.message.reply_text("✅ Đăng ký upcode thành công!")
        else:
            await update.message.reply_text(f"❌ Lỗi khi gửi form ({resp.status_code})")

    else:
        await update.message.reply_text("❓ Không rõ bạn muốn làm gì — dùng /start để mở menu.")

# ==== MAIN ====
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(menu_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.run_polling()

if __name__ == "__main__":
    main()
