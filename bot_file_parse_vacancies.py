import os
import requests
import logging
from time import sleep
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
import pandas as pd

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Токен бота
TOKEN = "7404822521:AAEg_yhZ6OP8XDB2FzGwQTqSRfeDIen84AM"

def extract_filters(text):
    salary_match = re.search(r'зарплата\s*>\s*(\d+)', text, re.IGNORECASE)
    employment_match = re.search(r'тип\s+занятости\s*:\s*(\w+)', text, re.IGNORECASE)

    filters = {
        "salary": int(salary_match.group(1)) if salary_match else None,
        "employment": employment_match.group(1) if employment_match else None
    }
    return filters

def get_vacancies(search_text: str, page: int = 0, per_page: int = 50, salary_from=None, employment=None):
    """Получает вакансии с hh.ru"""
    try:
        url = "https://api.hh.ru/vacancies"
        params = {
            "text": search_text,
            "page": page,
            "per_page": per_page,
            "area": 1,  # 1 - Москва
        }
        if salary_from:
            params["salary"] = salary_from
        if employment:
            params["employment"] = employment

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
        df = pd.DataFrame(vacancies, columns=['name', 'company', 'salary', 'url'])
        df.columns = ['Должность', 'Компания', 'Зарплата', 'Ссылка']
        
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

        clean_text = re.sub(r'зарплата\s*>\s*\d+', '', search_query, flags=re.IGNORECASE)
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
                    employment=filters["employment"]
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