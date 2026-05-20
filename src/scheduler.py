import os
import yaml
import logging
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from src.main import run_job, get_all_jobs
from src.utils.config_loader import load_main_config

logger = logging.getLogger("Core.Scheduler")

def parse_trigger(schedule_str: str):
    """
    Парсит строку расписания из config.yaml и возвращает соответствующий триггер APScheduler.
    Примеры форматов:
      - "cron:0 8 * * 1-5" (Каждый будний день в 8:00)
      - "interval:60"     (Каждые 60 минут)
    """
    if not schedule_str:
        return None
        
    try:
        type_part, value_part = schedule_str.split(":", 1)
        type_part = type_part.strip().lower()
        value_part = value_part.strip()
        
        if type_part == "cron":
            # Стандартный синтаксис cron: minute hour day month day_of_week
            args = value_part.split()
            if len(args) != 5:
                raise ValueError("Синтаксис Cron должен содержать 5 параметров (строка: 'минута час день месяц день_недели')")
            return CronTrigger(minute=args[0], hour=args[1], day=args[2], month=args[3], day_of_week=args[4])
            
        elif type_part == "interval":
            # Интервал в минутах
            minutes = int(value_part)
            return IntervalTrigger(minutes=minutes)
            
        else:
            logger.error(f"Неизвестный тип расписания: '{type_part}'. Допустимы 'cron' или 'interval'.")
            return None
            
    except Exception as e:
        logger.error(f"Ошибка парсинга строки расписания '{schedule_str}': {e}")
        return None

def start_scheduler():
    """
    Инициализирует и запускает фоновый планировщик задач.
    """
    logger.info("Инициализация внутреннего планировщика задач...")
    
    # Блокирующий шедулер забирает поток выполнения под себя и крутится в бесконечном цикле
    scheduler = BlockingScheduler()
    
    # Сканируем все доступные отчеты в папке /jobs
    all_jobs = get_all_jobs()
    active_jobs_count = 0
    
    for job_name in all_jobs:
        config_path = os.path.join("jobs", job_name, "config.yaml")
        if not os.path.exists(config_path):
            continue
            
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                job_config = yaml.safe_load(f)
                
            # Проверяем, включен ли отчет в принципе
            if not job_config.get("enabled", True):
                continue
                
            schedule_str = job_config.get("schedule")
            if not schedule_str:
                logger.info(f"Отчет '{job_name}' загружен (только ручной запуск, расписание не задано).")
                continue
                
            trigger = parse_trigger(schedule_str)
            if trigger:
                # Регистрируем задачу в шедулере
                # Свойство max_instances=1 гарантирует, что если отчет выполняется дольше, 
                # чем шаг расписания, второй такой же отчет параллельно не запустится.
                scheduler.add_job(
                    func=run_job,
                    trigger=trigger,
                    args=[job_name],
                    id=job_name,
                    max_instances=1,
                    name=job_config.get("name", job_name)
                )
                logger.info(f"📅 Задача '{job_name}' успешно поставлена в расписание: [{schedule_str}]")
                active_jobs_count += 1
                
        except Exception as e:
            logger.error(f"Не удалось поставить в расписание отчет '{job_name}': {e}", exc_info=True)

    if active_jobs_count == 0:
        logger.warning("Нет активных задач по расписанию. Планировщику нечего выполнять.")
        return

    logger.info(f"Планировщик успешно запущен. Активных задач по расписанию: {active_jobs_count}")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Планировщик остановлен пользователем или службой.")