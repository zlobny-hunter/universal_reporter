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
            CREATE TABLE IF NOT EXISTS job_states (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_name TEXT,
                last_run TEXT,
                status TEXT,
                error_message TEXT,
                run_type TEXT DEFAULT 'scheduler',
                run_user TEXT,
                parameters TEXT
            )
        """)
        # Add parameters column if table exists without it (for existing databases
        try:
            cursor.execute("ALTER TABLE job_states ADD COLUMN parameters TEXT")
        except sqlite3.OperationalError:
            # Column already exists, ignore error
            pass
        
        # Migrate old schema (job_name as PRIMARY KEY) to new schema (id as PRIMARY KEY)
        try:
            cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='job_states'")
            table_sql = cursor.fetchone()
            if table_sql and 'job_name TEXT PRIMARY KEY' in table_sql[0]:
                print("[DB MIGRATION] Migrating job_states table from old schema to new schema...")
                cursor.execute("ALTER TABLE job_states RENAME TO job_states_old")
                cursor.execute("""
                    CREATE TABLE job_states (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        job_name TEXT,
                        last_run TEXT,
                        status TEXT,
                        error_message TEXT,
                        run_type TEXT DEFAULT 'scheduler',
                        run_user TEXT,
                        parameters TEXT
                    )
                """)
                cursor.execute("""
                    INSERT INTO job_states (job_name, last_run, status, error_message, run_type, run_user, parameters)
                    SELECT job_name, last_run, status, error_message, run_type, run_user, parameters
                    FROM job_states_old
                """)
                cursor.execute("DROP TABLE job_states_old")
                conn.commit()
                print("[DB MIGRATION] Migration completed successfully.")
        except Exception as e:
            print(f"[DB MIGRATION] Migration not needed or failed: {e}")
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
                error_message TEXT
            )
        """)
        conn.commit()

def log_job_state(job_name: str, status: str, error_message: str = "", run_type: str = "scheduler", run_user: str = None, parameters: dict = None):
    """Записывает текущее состояние отчета (для вывода в UI)."""
    try:
        init_history_db()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Convert parameters dict to JSON string for storage
        import json
        params_json = json.dumps(parameters) if parameters else "{}"
        
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO job_states (job_name, last_run, status, error_message, run_type, run_user, parameters)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (job_name, now, status, error_message, run_type, run_user, params_json))
            conn.commit()
        logger.debug(f"Статус отчета '{job_name}' успешно сохранен в SQLite ({status}).")
    except Exception as e:
        logger.error(f"Не удалось записать статус отчета в SQLite: {e}")

def log_user_run(user_id: str, user_name: str, job_name: str, job_title: str, 
                 status: str, parameters: dict = None, error_message: str = ""):
    """Записывает историю запуска отчета пользователем."""
    try:
        init_history_db()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Convert parameters dict to JSON string for storage
        import json
        params_json = json.dumps(parameters) if parameters else "{}"
        
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO user_run_history 
                (user_id, user_name, job_name, job_title, run_time, status, parameters, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (str(user_id), user_name, job_name, job_title, now, status, params_json, error_message))
            
            # Also update job_states with manual run info
            cursor.execute("""
                INSERT INTO job_states (job_name, last_run, status, error_message, run_type, run_user, parameters)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (job_name, now, status, error_message, "manual", user_name, params_json))
            
            conn.commit()
        logger.info(f"Запуск отчета '{job_name}' пользователем '{user_name}' (ID: {user_id}) записан: {status}")
    except Exception as e:
        logger.error(f"Не удалось записать историю запуска пользователя: {e}")