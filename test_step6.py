import logging
import sqlite3
from src.utils.config_loader import setup_logging
from src.main import run_job

def main():
    setup_logging()
    logger = logging.getLogger("TestStep6")
    logger.info("--- Старт проверки Шага 6 ---")

    # 1. Запускаем валидный отчет по полному циклу
    run_job("test_report")
    
    # 2. Намеренно запускаем сломанный/несуществующий отчет для проверки алертинга
    logger.info("Тест защиты: запускаем несуществующий отчет...")
    run_job("ghost_report")

    # 3. Проверим, что SQLite база истории заполнилась правильными статусами
    logger.info("Проверяем содержимое базы данных run_history.db:")
    try:
        with sqlite3.connect("data/run_history.db") as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT job_name, last_run, status, error_message FROM job_states")
            rows = cursor.fetchall()
            for row in rows:
                print(f"\nОтчет: {row[0]}\nВремя: {row[1]}\nСтатус: {row[2]}\nОшибка: {row[3]}\n{'-'*30}")
    except Exception as e:
        logger.error(f"Не удалось прочесть тестовую БД SQLite: {e}")

    logger.info("--- Проверка Шага 6 завершена ---")

if __name__ == "__main__":
    main()