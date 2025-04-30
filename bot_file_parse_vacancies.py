import os
import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, ConversationHandler

# Этапы диалога
ASK_KEYWORD, ASK_SALARY, ASK_EMPLOYMENT, ASK_SCHEDULE, ASK_CITY = range(5)

# Карты фильтров
EMPLOYMENT_MAP = {
    "Полная занятость": "full",
    "Частичная занятость": "part",
    "Проектная занятость": "project",
    "Волонтёрство": "volunteer",
    "Стажировка": "probation"
}

SCHEDULE_MAP = {
    "Полный день": "fullDay",
    "Сменный график": "shift",
    "Гибкий график": "flexible",
    "Удалённая работа": "remote",
    "Вахтовый метод": "flyInFlyOut"
}

AREA_MAP = {
    "Москва": 1,
    "Санкт-Петербург": 2,
    "Новосибирск": 4,
    "Екатеринбург": 3,
    "Краснодар": 53,
    "Россия (вся)": 113
}

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Получение токена
TOKEN = os.environ.get("BOT_TOKEN", "7404822521:AAEg_yhZ6OP8XDB2FzGwQTqSRfeDIen84AM")
if not TOKEN:
    raise ValueError("BOT_TOKEN не задан в переменных окружения")

user_data_store = {}

def start(update: Update, context: CallbackContext) -> int:
    logger.info("Команда /start выполнена")
    update.message.reply_text("👋 Привет! Давай подберем тебе вакансии.\n\nВведите ключевое слово для поиска (например: Python разработчик):")
    return ASK_KEYWORD

def ask_salary(update: Update, context: CallbackContext) -> int:
    keyword = update.message.text.strip()
    logger.info(f"Пользователь ввел ключевое слово: {keyword}")
    user_data_store[update.effective_chat.id] = {"keyword": keyword}
    update.message.reply_text("💰 Укажите минимальную зарплату в рублях (например: 100000):")
    return ASK_SALARY

def ask_employment(update: Update, context: CallbackContext) -> int:
    try:
        salary = int(update.message.text.strip())
    except ValueError:
        logger.warning("Пользователь ввел некорректную зарплату")
        update.message.reply_text("❗ Пожалуйста, введите корректное число для зарплаты:")
        return ASK_SALARY

    user_data_store[update.effective_chat.id]["salary"] = salary
    # Формируем клавиатуру
    reply_keyboard = [[KeyboardButton(option)] for option in EMPLOYMENT_MAP.keys()]
    logger.info(f"Клавиатура для типа занятости: {reply_keyboard}")
    
    # Проверяем, что клавиатура содержит ожидаемые кнопки
    if not reply_keyboard:
        logger.error("Клавиатура пуста!")
        update.message.reply_text("Ошибка: не удалось сформировать клавиатуру. Попробуйте снова.")
        return ASK_SALARY

    # Отправляем сообщение с клавиатурой
    update.message.reply_text(
        "📄 Выберите тип занятости:",
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard,
            one_time_keyboard=True,
            resize_keyboard=True,
            input_field_placeholder="Выберите тип занятости"
        )
    )
    logger.info("Сообщение с клавиатурой отправлено")
    return ASK_EMPLOYMENT

def ask_schedule(update: Update, context: CallbackContext) -> int:
    employment = update.message.text.strip().title()
    logger.info(f"Пользователь выбрал тип занятости: {employment}")
    if employment not in EMPLOYMENT_MAP:
        logger.warning(f"Некорректный тип занятости: {employment}")
        reply_keyboard = [[KeyboardButton(option)] for option in EMPLOYMENT_MAP.keys()]
        update.message.reply_text(
            "❗ Пожалуйста, выберите тип занятости из предложенных вариантов:",
            reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
        )
        return ASK_EMPLOYMENT

    user_data_store[update.effective_chat.id]["employment"] = EMPLOYMENT_MAP[employment]
    reply_keyboard = [[KeyboardButton(option)] for option in SCHEDULE_MAP.keys()]
    update.message.reply_text(
        "📅 Выберите график работы:",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
    )
    return ASK_SCHEDULE

def ask_city(update: Update, context: CallbackContext) -> int:
    schedule = update.message.text.strip().title()
    logger.info(f"Пользователь выбрал график работы: {schedule}")
    if schedule not in SCHEDULE_MAP:
        reply_keyboard = [[KeyboardButton(option)] for option in SCHEDULE_MAP.keys()]
        update.message.reply_text(
            "❗ Пожалуйста, выберите график работы из предложенных вариантов:",
            reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
        )
        return ASK_SCHEDULE

    user_data_store[update.effective_chat.id]["schedule"] = SCHEDULE_MAP[schedule]
    reply_keyboard = [[KeyboardButton(option)] for option in AREA_MAP.keys()]
    update.message.reply_text(
        "📍 Выберите город:",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
    )
    return ASK_CITY

def perform_search(update: Update, context: CallbackContext) -> int:
    city = update.message.text.strip().title()
    area_id = AREA_MAP.get(city)
    if not area_id:
        reply_keyboard = [[KeyboardButton(option)] for option in AREA_MAP.keys()]
        update.message.reply_text(
            "❗ Пожалуйста, выберите город из предложенных вариантов:",
            reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
        )
        return ASK_CITY

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
    update.message.reply_text(summary, reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

def cancel(update: Update, context: CallbackContext) -> int:
    logger.info("Поиск отменен пользователем")
    update.message.reply_text("❌ Поиск отменен.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

def error_handler(update: Update, context: CallbackContext):
    logger.error(f"Ошибка: {context.error}")
    if update.message:
        update.message.reply_text("Произошла ошибка, попробуйте снова.")

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
    dp.add_error_handler(error_handler)

    logger.info("Бот запущен")
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()