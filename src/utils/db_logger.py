import os
import sqlite3
import logging
from datetime import datetime

logger = logging.getLogger("Utils.DBLogger")
# Определяем путь к БД относительно расположения этого файла
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(os.path.dirname(CURRENT_DIR))
DB_PATH = os.path.join(BASE_DIR, "data", "job_status.db")

def init_history_db():
    """Создает таблицу истории запусков, если её нет."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_run_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                user_name TEXT,
                job_name TEXT,
                job_title TEXT,
                run_time TEXT,
                status TEXT,
                parameters TEXT,
                error_message TEXT,
                start_type TEXT
            )
        """)
        conn.commit()


def log_user_run(user_id: str, user_name: str, job_name: str, job_title: str, 
                 status: str, parameters: dict = None, error_message: str = "", start_type: str = "local_user"):
    """Записывает историю запуска отчета пользователем."""
    try:
        print(f"[DB_LOGGER] Начало записи в БД: user_id={user_id}, user_name={user_name}, job_name={job_name}, status={status}, start_type={start_type}")
        print(f"[DB_LOGGER] Путь к БД: {DB_PATH}")
        
        init_history_db()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Convert parameters dict to JSON string for storage
        import json
        params_json = json.dumps(parameters) if parameters else "{}"
        
        print(f"[DB_LOGGER] Подключение к БД...")
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO user_run_history 
                (user_id, user_name, job_name, job_title, run_time, status, parameters, error_message, start_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (str(user_id), user_name, job_name, job_title, now, status, params_json, error_message, start_type))
            
            conn.commit()
            print(f"[DB_LOGGER] Запись успешно сохранена в БД")
        logger.info(f"Запуск отчета '{job_name}' пользователем '{user_name}' (ID: {user_id}) записан: {status}, start_type: {start_type}")
    except Exception as e:
        print(f"[DB_LOGGER ERROR] Ошибка записи в БД: {e}")
        import traceback
        print(f"[DB_LOGGER ERROR] Traceback: {traceback.format_exc()}")
        logger.error(f"Не удалось записать историю запуска пользователя: {e}")