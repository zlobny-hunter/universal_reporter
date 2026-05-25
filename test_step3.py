import logging
import yaml
import pandas as pd
from src.utils.config_loader import setup_logging
from src.qa.validator import validate_dataframe
from src.excel.writer import build_excel_workbook

def main():
    setup_logging()
    logger = logging.getLogger("TestStep3")
    logger.info("--- Старт проверки Шага 3 ---")

    # 1. Эмулируем чтение YAML-конфига отчета
    with open("jobs/person_report/config.yaml", "r", encoding="utf-8") as f:
        job_config = yaml.safe_load(f)

    # 2. Создаем тестовые данные (как будто получили из БД на Шаге 2)
    mock_data = pd.DataFrame([
        {"id": 1, "manager_name": "Иван Иванов", "amount": 55000, "report_generated_at": "2026-05-19"},
        {"id": 2, "manager_name": "Петр Петров", "amount": 73000, "report_generated_at": "2026-05-19"}
    ])

    try:
        # 3. Тестируем валидатор на корректных данных
        status = validate_dataframe(mock_data, job_config)
        
        if status == "PROCEED":
            # Формируем структуру данных для генератора: {"Имя вкладки": DataFrame}
            sheets_data = {"Эффективность": mock_data}
            
            # 4. Собираем Excel документ
            output_file = build_excel_workbook(sheets_data, job_config)
            logger.info(f"Успех! Файл собран и лежит тут: {output_file}")
            
        # 5. Тестируем валидатор на пустых данных, чтобы проверить защиту от «пустышек»
        logger.info("Проверка защиты: передаем пустой DataFrame...")
        empty_df = pd.DataFrame()
        validate_dataframe(empty_df, job_config) # Здесь код должен выбросить контролируемое исключение
        
    except ValueError as ve:
        logger.info(f"Защита валидатора отработала штатно: {ve}")
    except Exception as e:
        logger.critical(f"Ошибка во время теста: {e}", exc_info=True)

    logger.info("--- Проверка Шага 3 завершена ---")

if __name__ == "__main__":
    main()