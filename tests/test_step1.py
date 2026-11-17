import logging
from src.utils.config_loader import setup_logging, load_main_config

def main():
    # 1. Запускаем логгер
    setup_logging()
    logger = logging.getLogger("TestCore")
    
    logger.info("--- Старт проверки Шага 1 ---")
    
    # 2. Пробуем загрузить основной конфиг
    try:
        config = load_main_config()
        logger.info("Глобальный конфиг успешно прочитан!")
        
        # Проверим, что данные внутри бьются по секциям
        db_host = config.get("database", {}).get("host")
        logger.debug(f"Тестовое чтение из конфига. Хост БД: {db_host}")
        
    except Exception as e:
        logger.error(f"Не удалось загрузить конфиг: {e}", exc_info=True)
        
    logger.info("--- Проверка Шага 1 завершена ---")

if __name__ == "__main__":
    main()