import os
import re
import logging
import requests
from time import sleep
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Updater, CommandHandler, MessageHandler, Filters,
    CallbackContext, ConversationHandler
)
from bs4 import BeautifulSoup
import pandas as pd

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("BOT_TOKEN")
if not TOKEN:
    raise ValueError("Переменная окружения BOT_TOKEN не установлена")

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

(KEYWORD, SALARY, EMPLOYMENT, SCHEDULE, CITY) = range(5)
user_data = {}

def start(update: Update, context: CallbackContext):
    update.message.reply_text("Введите ключевое слово для поиска вакансий:")
    return KEYWORD

def keyword_handler(update: Update, context: CallbackContext):
    user_data[update.effective_user.id] = {"keyword": update.message.text}
    update.message.reply_text("Укажите зарплату от (числом):")
    return SALARY

def salary_handler(update: Update, context: CallbackContext):
    try:
        user_data[update.effective_user.id]["salary"] = int(update.message.text)
    except ValueError:
        update.message.reply_text("Пожалуйста, введите число")
        return SALARY

    keyboard = [[k] for k in EMPLOYMENT_MAP.keys()]
    update.message.reply_text(
        "Выберите тип занятости:",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    )
    return EMPLOYMENT

def employment_handler(update: Update, context: CallbackContext):
    user_data[update.effective_user.id]["employment"] = EMPLOYMENT_MAP.get(update.message.text)

    keyboard = [[k] for k in SCHEDULE_MAP.keys()]
    update.message.reply_text(
        "Выберите график работы:",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    )
    return SCHEDULE

def schedule_handler(update: Update, context: CallbackContext):
    user_data[update.effective_user.id]["schedule"] = SCHEDULE_MAP.get(update.message.text)
    update.message.reply_text("Укажите город:")
    return CITY

def city_handler(update: Update, context: CallbackContext):
    city = update.message.text.lower()
    user_data[update.effective_user.id]["area"] = AREA_MAP.get(city, 113)
    user_data[update.effective_user.id]["city_name"] = city.title()
    update.message.reply_text("Начинаю поиск вакансий...")
    perform_search(update, context)
    return ConversationHandler.END

def clean_html(html_text):
    return BeautifulSoup(html_text, "html.parser").get_text()

def get_full_description(vacancy_id):
    try:
        url = f"https://api.hh.ru/vacancies/{vacancy_id}"
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
        response.raise_for_status()
        return response.json().get("description", "Нет описания")
    except:
        return "Нет описания"

def get_vacancies(params):
    all_vacancies = []
    for page in range(3):
        try:
            url = "https://api.hh.ru/vacancies"
            query = {
                "text": params["keyword"],
                "area": params["area"],
                "salary": params["salary"],
                "employment": params["employment"],
                "schedule": params["schedule"],
                "page": page,
                "per_page": 50
            }
            response = requests.get(url, params=query, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
            response.raise_for_status()
            data = response.json()
            for item in data.get("items", []):
                salary = item.get("salary")
                salary_info = "Не указана"
                if salary:
                    salary_info = f"{salary.get('from', '?')} - {salary.get('to', '?')} {salary.get('currency', '')}"
                all_vacancies.append({
                    "name": item.get("name", "Название не указано"),
                    "company": item.get("employer", {}).get("name", "Компания не указана"),
                    "salary": salary_info,
                    "description": clean_html(get_full_description(item["id"])),
                    "url": item.get("alternate_url", "#")
                })
            sleep(1)
        except Exception as e:
            logger.warning(f"Ошибка при загрузке страницы {page}: {e}")
    return all_vacancies

def save_to_xlsx(vacancies, filename="vacancies.xlsx"):
    try:
        df = pd.DataFrame(vacancies)
        df.columns = ['Должность', 'Компания', 'Зарплата', 'Описание', 'Ссылка']
        filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
        df.to_excel(filepath, index=False, engine='openpyxl')
        return filepath
    except Exception as e:
        logger.error(f"Ошибка при сохранении файла: {e}")
        return None

def perform_search(update: Update, context: CallbackContext):
    params = user_data[update.effective_user.id]
    vacancies = get_vacancies(params)
    if not vacancies:
        update.message.reply_text("Вакансии не найдены.")
        return

    filepath = save_to_xlsx(vacancies)
    if filepath:
        with open(filepath, 'rb') as f:
            update.message.reply_document(f, filename="vacancies.xlsx", caption=f"Найдено {len(vacancies)} вакансий")

        preview = "\n".join(f"{i+1}. {v['name']} ({v['company']}) - {v['salary']}\n{v['url']}" for i, v in enumerate(vacancies[:5]))
        update.message.reply_text(f"📋 Примеры вакансий:\n\n{preview}")


def cancel(update: Update, context: CallbackContext):
    update.message.reply_text("Поиск отменён.")
    return ConversationHandler.END

def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            KEYWORD: [MessageHandler(Filters.text & ~Filters.command, keyword_handler)],
            SALARY: [MessageHandler(Filters.text & ~Filters.command, salary_handler)],
            EMPLOYMENT: [MessageHandler(Filters.text & ~Filters.command, employment_handler)],
            SCHEDULE: [MessageHandler(Filters.text & ~Filters.command, schedule_handler)],
            CITY: [MessageHandler(Filters.text & ~Filters.command, city_handler)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    dp.add_handler(conv_handler)
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()