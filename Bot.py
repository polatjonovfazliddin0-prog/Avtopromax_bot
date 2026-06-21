import csv
import logging
import os
from datetime import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "PUT_YOUR_TOKEN_HERE")
ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID", "PUT_YOUR_CHAT_ID_HERE")

LEADS_FILE = "leads.csv"

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

Q1, Q2, Q3, Q4, Q5, OFFER, ASK_NAME, ASK_PHONE = range(8)

QUESTIONS = [
    {
        "text": "1-savol: Piyodalar o'tish joyida piyoda ko'rinsa, haydovchi nima qilishi kerak?",
        "options": [("To'xtab, o'tkazib yuborish", True), ("Signal berib o'tib ketish", False), ("Tezlikni oshirish", False)],
    },
    {
        "text": "2-savol: \"To'xtash taqiqlangan\" belgisi qanday shaklda bo'ladi?",
        "options": [("Doira, qizil chiziq bilan", True), ("Uchburchak", False), ("Kvadrat", False)],
    },
    {
        "text": "3-savol: Chorrahada svetofor ishlamasa, kim ustun huquqga ega?",
        "options": [("O'ng tomondan keladigan transport", True), ("Chap tomondan keladigan transport", False), ("Tezroq yetib kelgan", False)],
    },
    {
        "text": "4-savol: Avtomobilda xavfsizlik kamari taqish majburiymi?",
        "options": [("Ha, doimo", True), ("Faqat shahar tashqarisida", False), ("Faqat haydovchi uchun", False)],
    },
    {
        "text": "5-savol: \"Bolalar\" ogohlantiruvchi belgisi qayerda o'rnatiladi?",
        "options": [("Maktab/bolalar muassasasi yaqinida", True), ("Faqat shoshilinch holatda", False), ("Faqat tunda", False)],
    },
]


def build_quiz_keyboard(question_index: int) -> InlineKeyboardMarkup:
    opts = QUESTIONS[question_index]["options"]
    buttons = [
        [InlineKeyboardButton(text, callback_data=f"ans_{question_index}_{i}_{ 'correct' if is_correct else 'wrong' }")]
        for i, (text, is_correct) in enumerate(opts)
    ]
    return InlineKeyboardMarkup(buttons)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["score"] = 0
    welcome_text = (
        "Assalomu alaykum! 🚗\n\n"
        "Avto.Promax — 10 kunda haydovchilik guvohnomasi olish kursiga xush kelibsiz!\n\n"
        "Boshlashdan oldin, bilimingizni tekshirib ko'ramiz — 5 ta qiziqarli savol bilan kichik test."
    )
    await update.message.reply_text(welcome_text)
    await update.message.reply_text(QUESTIONS[0]["text"], reply_markup=build_quiz_keyboard(0))
    return Q1


async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    _, q_index_str, _, result = query.data.split("_")
    q_index = int(q_index_str)

    if result == "correct":
        context.user_data["score"] = context.user_data.get("score", 0) + 1
        feedback = "✅ To'g'ri!"
    else:
        feedback = "❌ Noto'g'ri."

    next_index = q_index + 1

    if next_index < len(QUESTIONS):
        await query.edit_message_text(f"{feedback}\n\n{QUESTIONS[next_index]['text']}", reply_markup=build_quiz_keyboard(next_index))
        return Q1 + next_index
    else:
        score = context.user_data.get("score", 0)
        await query.edit_message_text(
            f"{feedback}\n\nTest tugadi! Siz {len(QUESTIONS)} ta savoldan {score} tasiga to'g'ri javob berdingiz.\n\n"
            f"Sizga mos kurs guruhimiz bor — 10 kunda 100% kafolat bilan guvohnoma olishni xohlaysizmi?"
        )
        keyboard = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("Ha, ro'yxatdan o'tmoqchiman ✅", callback_data="register_yes")],
                [InlineKeyboardButton("Yo'q, hozircha kerak emas", callback_data="register_no")],
            ]
        )
        await context.bot.send_message(chat_id=query.message.chat_id, text="Tanlovingizni bildiring:", reply_markup=keyboard)
        return OFFER


async def handle_offer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == "register_yes":
        await query.edit_message_text("Ajoyib! 😊 Ro'yxatdan o'tish uchun ismingizni yozib yuboring:")
        return ASK_NAME
    else:
        await query.edit_message_text(
            "Tushunarli! Fikringizni o'zgartirsangiz, istalgan vaqtda /start buyrug'ini yuborib qaytib kelishingiz mumkin. 👋"
        )
        return ConversationHandler.END


async def ask_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["name"] = update.message.text
    contact_button = KeyboardButton(text="📱 Raqamni yuborish", request_contact=True)
    keyboard = ReplyKeyboardMarkup([[contact_button]], resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text(
        "Rahmat! Endi telefon raqamingizni pastdagi tugma orqali yuboring (yoki qo'lda yozing):",
        reply_markup=keyboard,
    )
    return ASK_PHONE


async def ask_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.contact:
        phone = update.message.contact.phone_number
    else:
        phone = update.message.text

    name = context.user_data.get("name", "Noma'lum")
    score = context.user_data.get("score", 0)
    username = update.message.from_user.username or "yo'q"
    chat_id = update.message.chat_id

    save_lead(name, phone, username, chat_id, score)

    await update.message.reply_text(
        "Rahmat! ✅ Ma'lumotlaringiz qabul qilindi.\nTez orada operatorlarimiz siz bilan bog'lanadi!",
        reply_markup=ReplyKeyboardRemove(),
    )

    if ADMIN_CHAT_ID and ADMIN_CHAT_ID != "PUT_YOUR_CHAT_ID_HERE":
        admin_text = (
            f"🆕 Yangi lead!\n\n"
            f"Ism: {name}\n"
            f"Telefon: {phone}\n"
            f"Telegram: @{username}\n"
            f"Test natijasi: {score}/{len(QUESTIONS)}\n"
            f"Vaqt: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )
        await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=admin_text)

    return ConversationHandler.END


def save_lead(name: str, phone: str, username: str, chat_id: int, score: int) -> None:
    file_exists = os.path.isfile(LEADS_FILE)
    with open(LEADS_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Sana", "Ism", "Telefon", "Username", "ChatID", "Test natijasi"])
        writer.writerow([datetime.now().strftime("%Y-%m-%d %H:%M"), name, phone, username, chat_id, f"{score}/{len(QUESTIONS)}"])


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Bekor qilindi. Qaytadan boshlash uchun /start yuboring.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


def main() -> None:
    if BOT_TOKEN == "PUT_YOUR_TOKEN_HERE":
        raise RuntimeError("BOT_TOKEN sozlanmagan!")

    application = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            Q1: [CallbackQueryHandler(handle_answer, pattern="^ans_")],
            Q2: [CallbackQueryHandler(handle_answer, pattern="^ans_")],
            Q3: [CallbackQueryHandler(handle_answer, pattern="^ans_")],
            Q4: [CallbackQueryHandler(handle_answer, pattern="^ans_")],
            Q5: [CallbackQueryHandler(handle_answer, pattern="^ans_")],
            OFFER: [CallbackQueryHandler(handle_offer, pattern="^register_")],
            ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_name)],
            ASK_PHONE: [MessageHandler((filters.CONTACT | filters.TEXT) & ~filters.COMMAND, ask_phone)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)

    logger.info("Bot ishga tushdi...")
    application.run_polling()


if __name__ == "__main__":
    main()
