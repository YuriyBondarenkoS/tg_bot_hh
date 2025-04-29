import os
import re
import requests
import logging
from time import sleep
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
from bs4 import BeautifulSoup
import pandas as pd

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Токен бота
TOKEN = os.environ.get("BOT_TOKEN")
if not TOKEN:
    raise ValueError("Переменная окружения BOT_TOKEN не установлена")

# Карта городов и их ID на hh.ru
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
    "краснодар": 53  # ← добавлен Краснодар
}

SCHEDULE_MAP = {
    "полный день": "fullDay",
    "сменный график": "shift",
    "гибкий график": "flexible",
    "удалённая работа": "remote",
    "вахтовый метод": "flyInFlyOut"
}

def extract_area(text):
    for city, area_id in AREA_MAP.items():
        if city in text.lower():
            return area_id, city
    return 113, None  # По умолчанию — вся Россия

def clean_html(html_text):
    return BeautifulSoup(html_text, "html.parser").get_text()

def get_full_description(vacancy_id):
    try:
        url = f"https://api.hh.ru/vacancies/{vacancy_id}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data.get("description", "Нет полного описания")
    except Exception as e:
        logger.warning(f"Не удалось получить полное описание для id {vacancy_id}: {e}")
        return "Нет полного описания"

def extract_filters(text):
    salary_match = re.search(r'зарплата\s*>\s*(\d+)', text, re.IGNORECASE)
    employment_match = re.search(r'тип\s+занятости\s*:\s*(\w+)', text, re.IGNORECASE)
    schedule_match = re.search(r'график\s+работы\s*:\s*([\w\s\-]+)', text, re.IGNORECASE)

    filters = {
        "salary": int(salary_match.group(1)) if salary_match else None,
        "employment": employment_match.group(1) if employment_match else None
        "schedule": schedule_match.group(1).strip().lower() if schedule_match else None
    }
    return filters

def get_vacancies(search_text: str, page: int = 0, per_page: int = 50, salary_from=None, employment=None, schedule=None, area=1):
    """Получает вакансии с hh.ru"""
    try:
        url = "https://api.hh.ru/vacancies"
        params = {
            "text": search_text,
            "page": page,
            "per_page": per_page,
            "area": area,  # 1 - Москва по умолчанию
        }
        if salary_from:
            params["salary"] = salary_from
        if employment:
            params["employment"] = employment
        if schedule:
            schedule_api = SCHEDULE_MAP.get(schedule.lower())
            if schedule_api:
                params["schedule"] = schedule_api

        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Ошибка при запросе к API: {e}")
        return None

def parse_vacancies(data: dict):
    """Парсит данные вакансий"""
    if not data or 'items' not in data:
        return []
    
    vacancies = []
    for item in data.get("items", []):
        try:
            salary = item.get("salary")
            if salary is None:
                salary_info = "Не указана"
            else:
                salary_from = salary.get('from', '?')
                salary_to = salary.get('to', '?')
                currency = salary.get('currency', '')
                salary_info = f"{salary_from} - {salary_to} {currency}".strip()
            
            vacancies.append({
                "name": item.get("name", "Название не указано"),
                "company": item.get("employer", {}).get("name", "Компания не указана"),
                "salary": salary_info,
                "description": clean_html(get_full_description(item["id"])),
                "url": item.get("alternate_url", "#"),
            })
        except Exception as e:
            logger.warning(f"Ошибка парсинга вакансии: {e}")
    return vacancies

def save_to_xlsx(vacancies: list, filename: str = "vacancies.xlsx"):
    """Сохраняет вакансии в XLSX"""
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        filepath = os.path.join(script_dir, filename)
        
        # Создаем DataFrame
        df = pd.DataFrame(vacancies, columns=['name', 'company', 'salary', 'description', 'url'])
        df.columns = ['Должность', 'Компания', 'Зарплата', 'Описание', 'Ссылка']
        
        # Сохраняем в XLSX
        df.to_excel(filepath, index=False, engine='openpyxl')
        
        return filepath
    except Exception as e:
        logger.error(f"Ошибка сохранения XLSX: {e}")
        return None

def start(update: Update, context: CallbackContext):
    """Обработчик команды /start"""
    try:
        update.message.reply_text(
            "Привет! Я бот для поиска вакансий с hh.ru\n"
            "Отправь мне название профессии (например: Python разработчик)\n\n"
            "Дополнительно можно указать:\n"
            "- зарплата > 100000\n"
            "- тип занятости: full\n"
            "Пример: Python зарплата > 150000 тип занятости: part"
        )
    except Exception as e:
        logger.error(f"Ошибка в команде /start: {e}")

def handle_message(update: Update, context: CallbackContext):
    """Обработчик текстовых сообщений"""
    try:
        search_query = update.message.text
        filters = extract_filters(search_query)

        area_id, area_name = extract_area(search_query)
        clean_text = search_query 

        if area_name:
            clean_text = re.sub(r'в\s+' + re.escape(area_name), '', clean_text, flags=re.IGNORECASE)

        clean_text = re.sub(r'зарплата\s*>\s*\d+', '', clean_text, flags=re.IGNORECASE)
        clean_text = re.sub(r'тип\s+занятости\s*:\s*\w+', '', clean_text, flags=re.IGNORECASE).strip()


        logger.info(f"Получен запрос: {search_query}")
        update.message.reply_text(f"🔍 Ищу вакансии по запросу: {search_query}...")
        
        all_vacancies = []
        for page in range(3):  # Парсим 3 страницы
            try:
                data = get_vacancies(
                    clean_text,
                    page=page,
                    salary_from=filters["salary"],
                    employment=filters["employment"],
                    schedule=filters["schedule"],
                    area=area_id
                )
                if data:
                    all_vacancies.extend(parse_vacancies(data))
                sleep(1)  # Задержка между запросами
            except Exception as e:
                logger.warning(f"Ошибка при обработке страницы {page}: {e}")
        
        if not all_vacancies:
            update.message.reply_text("😕 Вакансий не найдено")
            return
            
        xlsx_path = save_to_xlsx(all_vacancies)
        if xlsx_path:
            try:
                with open(xlsx_path, 'rb') as file:
                    update.message.reply_document(
                        document=file,
                        caption=f"Найдено {len(all_vacancies)} вакансий\nФайл в формате XLSX",
                        filename="vacancies.xlsx"
                    )
                
                preview = "\n".join(
                    f"{i+1}. {v['name']} ({v['company']}) - {v['salary']}\n{v['url']}"
                    for i, v in enumerate(all_vacancies[:5])
                )
                update.message.reply_text(f"📋 Примеры вакансий:\n\n{preview}")
            except Exception as e:
                logger.error(f"Ошибка отправки файла: {e}")
                update.message.reply_text("⚠️ Произошла ошибка при отправке результатов")
    except Exception as e:
        logger.error(f"Ошибка обработки сообщения: {e}")
        update.message.reply_text("⚠️ Произошла внутренняя ошибка бота")

def main():
    """Запуск бота"""
    try:
        logger.info("Запуск бота...")
        updater = Updater(TOKEN, use_context=True)
        dp = updater.dispatcher
        
        dp.add_handler(CommandHandler("start", start))
        dp.add_handler(CommandHandler("help", start))
        dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
        
        logger.info("Бот успешно запущен и ожидает сообщений...")
        updater.start_polling()
        updater.idle()
    except Exception as e:
        logger.critical(f"Ошибка запуска бота: {e}")

if __name__ == "__main__":
    main()