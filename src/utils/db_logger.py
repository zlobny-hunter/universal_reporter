import os
import sqlite3
import logging
from datetime import datetime

logger = logging.getLogger("Utils.DBLogger")
DB_PATH = "data/run_history.db"

def init_history_db():
    """Создает таблицу истории запусков, если её нет."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS job_states (
                job_name TEXT PRIMARY KEY,
                last_run TEXT,
                status TEXT,
                error_message TEXT
            )
        """)
        conn.commit()

def log_job_state(job_name: str, status: str, error_message: str = ""):
    """Записывает текущее состояние отчета (для вывода в UI)."""
    try:
        init_history_db()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO job_states (job_name, last_run, status, error_message)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(job_name) DO UPDATE SET
                    last_run = excluded.last_run,
                    status = excluded.status,
                    error_message = excluded.error_message
            """, (job_name, now, status, error_message))
            conn.commit()
        logger.debug(f"Статус отчета '{job_name}' успешно сохранен в SQLite ({status}).")
    except Exception as e:
        logger.error(f"Не удалось записать статус отчета в SQLite: {e}")