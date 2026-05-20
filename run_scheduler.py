from src.utils.config_loader import setup_logging
from src.scheduler import start_scheduler

if __name__ == "__main__":
    # Инициализируем систему логирования
    setup_logging()
    
    # Стартуем бесконечный цикл планировщика
    start_scheduler()