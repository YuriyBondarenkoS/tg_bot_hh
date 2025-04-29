import os
import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, ConversationHandler

# Этапы диалога
ASK_KEYWORD, ASK_SALARY, ASK_EMPLOYMENT, ASK_SCHEDULE, ASK_CITY = range(5)

AREA_MAP = {
    "москва": 1,
    "санкт-петербург": 2,
    "новосибирск": 4,
    "екатеринбург": 3,
    "нижний новгород": 66,
    "казань": 88,
    "челябинск": 104,
    "омск": 68,
    "самара": 78,
    "ростов-на-дону": 76,
    "уфа": 99,
    "красноярск": 54,
    "пермь": 72,
    "воронеж": 106,
    "волгоград": 102,
    "краснодар": 53
}

SCHEDULE_MAP = {
    "Полный день": "fullDay",
    "Сменный график": "shift",
    "Гибкий график": "flexible",
    "Удалённая работа": "remote",
    "Вахтовый метод": "flyInFlyOut"
}

EMPLOYMENT_MAP = {
    "Полная занятость": "full",
    "Частичная занятость": "part",
    "Проектная занятость": "project",
    "Волонтёрство": "volunteer",
    "Стажировка": "probation"
}

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Получение токена
TOKEN = os.environ.get("BOT_TOKEN")
if not TOKEN:
    raise ValueError("BOT_TOKEN не задан в переменных окружения")

user_data_store = {}

def start(update: Update, context: CallbackContext) -> int:
    update.message.reply_text("👋 Привет! Давай подберем тебе вакансии.\n\nВведите ключевое слово для поиска (например: Python разработчик):")
    return ASK_KEYWORD

def ask_salary(update: Update, context: CallbackContext) -> int:
    user_data_store[update.effective_chat.id] = {"keyword": update.message.text.strip()}
    update.message.reply_text("💰 Укажите минимальную зарплату в рублях (например: 100000):")
    return ASK_SALARY

def ask_employment(update: Update, context: CallbackContext) -> int:
    try:
        salary = int(update.message.text.strip())
    except ValueError:
        update.message.reply_text("❗ Пожалуйста, введите корректное число для зарплаты:")
        return ASK_SALARY

    user_data_store[update.effective_chat.id]["salary"] = salary
    reply_keyboard = [[KeyboardButton(option)] for option in EMPLOYMENT_MAP.keys()]
    update.message.reply_text(
        "📄 Выберите тип занятости:",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
    )
    return ASK_EMPLOYMENT

def ask_schedule(update: Update, context: CallbackContext) -> int:
    employment = update.message.text.strip()
    if employment not in EMPLOYMENT_MAP:
        update.message.reply_text("❗ Пожалуйста, выберите тип занятости из предложенных вариантов:")
        return ASK_EMPLOYMENT

    user_data_store[update.effective_chat.id]["employment"] = EMPLOYMENT_MAP[employment]
    reply_keyboard = [[KeyboardButton(option)] for option in SCHEDULE_MAP.keys()]
    update.message.reply_text(
        "📅 Выберите график работы:",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
    )
    return ASK_SCHEDULE

def ask_city(update: Update, context: CallbackContext) -> int:
    schedule = update.message.text.strip()
    if schedule not in SCHEDULE_MAP:
        update.message.reply_text("❗ Пожалуйста, выберите график работы из предложенных вариантов:")
        return ASK_SCHEDULE

    user_data_store[update.effective_chat.id]["schedule"] = SCHEDULE_MAP[schedule]
    cities = ", ".join(AREA_MAP.keys())
    update.message.reply_text(f"📍 Укажите город (возможные варианты: {cities}):", reply_markup=ReplyKeyboardRemove())
    return ASK_CITY

def perform_search(update: Update, context: CallbackContext) -> int:
    city = update.message.text.strip()
    area_id = AREA_MAP.get(city.title(), 113)  # По умолчанию Россия
    user_data_store[update.effective_chat.id]["area"] = area_id

    data = user_data_store[update.effective_chat.id]
    summary = (
        f"🔍 Поиск вакансий:\n"
        f"Ключевое слово: {data['keyword']}\n"
        f"Зарплата от: {data['salary']} руб.\n"
        f"Тип занятости: {data['employment']}\n"
        f"График работы: {data['schedule']}\n"
        f"Город (ID): {data['area']}\n\n"
        "(Тут будет запрос к API и вывод вакансий)"
    )
    update.message.reply_text(summary)
    return ConversationHandler.END

def cancel(update: Update, context: CallbackContext) -> int:
    update.message.reply_text("❌ Поиск отменен.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ASK_KEYWORD: [MessageHandler(Filters.text & ~Filters.command, ask_salary)],
            ASK_SALARY: [MessageHandler(Filters.text & ~Filters.command, ask_employment)],
            ASK_EMPLOYMENT: [MessageHandler(Filters.text & ~Filters.command, ask_schedule)],
            ASK_SCHEDULE: [MessageHandler(Filters.text & ~Filters.command, ask_city)],
            ASK_CITY: [MessageHandler(Filters.text & ~Filters.command, perform_search)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    dp.add_handler(conv_handler)

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()