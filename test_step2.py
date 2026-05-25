import logging
from src.utils.config_loader import setup_logging, load_main_config
from src.database.db_client import DBClient

def main():
    setup_logging()
    logger = logging.getLogger("TestStep2")
    logger.info("--- Старт проверки Шага 2 ---")

    try:
        # 1. Загружаем основной конфиг
        config = load_main_config()
        
        # Для локального теста принудительно переключаем на sqlite, 
        # чтобы не требовать поднятого Postgres/MariaDB прямо сейчас
        config["database"]["dialect"] = "sqlite" 
        
        # 2. Инициализируем клиент БД
        db = DBClient(config["database"])
        
        # 3. Пытаемся прочесть и выполнить наш тестовый SQL-файл
        sql_file_path = "jobs/person_report/query.sql"
        
        # Передадим кастомные параметры (проверим работу шаблонизатора)
        custom_params = {"current_date": "2026-05-19"} 
        
        df = db.execute_sql_file(file_path=sql_file_path, params=custom_params)
        
        # 4. Выводим результат в логи для проверки структуры
        logger.info("Данные успешно получены в DataFrame:")
        print("\n", df.to_string(index=False))
        
    except Exception as e:
        logger.critical(f"Тест Шага 2 провален: {e}", exc_info=True)

    logger.info("--- Проверка Шага 2 завершена ---")

if __name__ == "__main__":
    main()