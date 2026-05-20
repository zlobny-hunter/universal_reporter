import os
import logging
import yaml

from src.utils.config_loader import load_main_config
from src.database.db_client import DBClient
from src.qa.validator import validate_dataframe
from src.excel.writer import build_excel_workbook
from src.delivery import dispatch_delivery
from src.monitoring.alerts import send_admin_alert
from src.utils.db_logger import log_job_state

logger = logging.getLogger("Core.Orchestrator")

def run_job(job_name: str):
    """
    Запускает полный цикл генерации и дистрибуции отчета.
    """
    logger.info(f"===> Накатываем выполнение отчета: {job_name} <===")
    
    # 1. Загрузка глобального конфига
    try:
        global_config = load_main_config()
    except Exception as e:
        # Без глобального конфига мы даже не знаем куда слать алерт, просто пишем в лог
        logger.critical(f"Не удалось загрузить глобальный main.toml: {e}")
        return

    job_dir = os.path.join("jobs", job_name)
    config_path = os.path.join(job_dir, "config.yaml")
    
    # Проверяем существование отчета
    if not os.path.exists(config_path):
        error_text = f"Конфигурационный файл отчета {config_path} не найден."
        send_admin_alert(error_text, global_config)
        log_job_state(job_name, "Ошибка", error_text)
        return

    try:
        # 2. Парсинг конфига отчета
        with open(config_path, "r", encoding="utf-8") as f:
            job_config = yaml.safe_load(f)
            
        if not job_config.get("enabled", True):
            logger.info(f"Отчет '{job_name}' отключен флагом enabled=false. Пропуск.")
            return

        # 3. Извлечение данных из БД
        # На время локальных тестов переключаем на sqlite
        global_config["database"]["dialect"] = "sqlite"
        db = DBClient(global_config["database"])
        
        sheets_data = {}
        wb_config = job_config.get("workbook", {})
        
        for sheet_cfg in wb_config.get("sheets", []):
            sheet_name = sheet_cfg.get("name")
            sql_file_name = sheet_cfg.get("sql_file")
            sql_file_path = os.path.join(job_dir, sql_file_name)
            
            # Тянем данные
            df = db.execute_sql_file(sql_file_path)
            
            # 4. Валидация данных (QA)
            qa_status = validate_dataframe(df, job_config)
            if qa_status == "SKIP":
                log_job_state(job_name, "Пропущен (Пустой)")
                return
                
            sheets_data[sheet_name] = df

        # 5. Сборка книги Excel
        excel_file_path = build_excel_workbook(sheets_data, job_config)
        
        # 6. Дистрибуция получателям
        delivery_cfg = job_config.get("delivery", {})
        dispatch_delivery(excel_file_path, delivery_cfg, global_config)
        
        # 7. Запись успешного статуса в историю
        log_job_state(job_name, "Успешно")
        logger.info(f"===> Отчет '{job_name}' успешно выполнен! <===")

    except Exception as err:
        # Ловим абсолютно любую непредвиденную ошибку на любом этапе конвейера
        error_msg = f"Ошибка в отчете '{job_name}': {str(err)}"
        
        # Отправляем экстренное уведомление админу
        send_admin_alert(error_msg, global_config)
        
        # Записываем ошибку в базу для UI
        log_job_state(job_name, "Ошибка", error_msg)

def get_all_jobs() -> list:
    """Вспомогательная функция: возвращает список папок отчетов из директории /jobs"""
    jobs_dir = "jobs"
    if not os.path.exists(jobs_dir):
        return []
    return [d for d in os.listdir(jobs_dir) if os.path.isdir(os.path.join(jobs_dir, d))]