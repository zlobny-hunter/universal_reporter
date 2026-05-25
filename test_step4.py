import os
import logging
import yaml
from src.utils.config_loader import setup_logging, load_main_config
from src.delivery import dispatch_delivery

def main():
    setup_logging()
    logger = logging.getLogger("TestStep4")
    logger.info("--- Старт проверки Шага 4 ---")

    # 1. Загружаем глобальный конфиг (для SMTP) и конфиг отчета
    global_config = load_main_config()
    with open("jobs/person_report/config.yaml", "r", encoding="utf-8") as f:
        job_config = yaml.safe_load(f)

    # 2. Нам нужен файл для отправки. 
    # Если вы не удаляли результаты шага 3, возьмем файл из папки output/
    output_dir = "output"
    files = [os.path.join(output_dir, f) for f in os.listdir(output_dir) if f.endswith('.xlsx')]
    
    if not files:
        logger.error("Тестовый excel-файл в папке 'output' не найден. Пожалуйста, запустите сначала test_step3.py")
        return
        
    test_file_path = files[0]
    logger.info(f"Используем для теста файл: {test_file_path}")

    # 3. Принудительно правим конфиг для теста, чтобы проверить локальное сохранение в текущую папку проекта
    job_config["delivery"]["local"]["target_path"] = os.path.abspath("final_archive_test")
    job_config["delivery"]["local"]["enabled"] = True

    # 4. Вызываем фабрику дистрибуции
    try:
        dispatch_delivery(
            file_path=test_file_path, 
            job_delivery_config=job_config.get("delivery", {}), 
            global_config=global_config
        )
        logger.info("Проверка распределения завершена успешно.")
    except Exception as e:
        logger.critical(f"Ошибка фабрики дистрибуции: {e}", exc_info=True)

    logger.info("--- Проверка Шага 4 завершена ---")

if __name__ == "__main__":
    main()