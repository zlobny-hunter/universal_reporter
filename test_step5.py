import os
import logging
import yaml
from src.utils.config_loader import setup_logging, load_main_config
from src.delivery import dispatch_delivery

def main():
    setup_logging()
    logger = logging.getLogger("TestStep5")
    logger.info("--- Старт проверки Шага 5 ---")

    global_config = load_main_config()
    
    # Создадим временную конфигурацию отчета прямо в коде для теста
    mock_job_delivery = {
        "local": {"enabled": False, "target_path": "test"},
        "nextcloud": {"enabled": False, "remote_path": "TestDir"},
        "yandex_messenger": {"enabled": False, "chat_id": "123", "caption": "Test"}
    }

    output_dir = "output"
    files = [os.path.join(output_dir, f) for f in os.listdir(output_dir) if f.endswith('.xlsx')]
    if not files:
        logger.error("Пожалуйста, запустите test_step3.py, чтобы в папке 'output' лежал файл.")
        return
    test_file = files[0]

    logger.info("Тестируем реакцию фабрики на новые каналы (все в состоянии enabled=False)...")
    try:
        dispatch_delivery(test_file, mock_job_delivery, global_config)
        logger.info("Фабрика успешно обработала структуру без падений.")
    except Exception as e:
        logger.critical(f"Ошибка теста фабрики: {e}", exc_info=True)

    logger.info("--- Проверка Шага 5 завершена ---")

if __name__ == "__main__":
    main()