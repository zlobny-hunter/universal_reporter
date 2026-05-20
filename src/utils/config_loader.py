import os
import toml
import logging
import logging.config

def setup_logging(config_path: str = "config/logging.toml"):
    """Инициализация логирования на основе файла конфигурации."""
    # Создаем папку для логов, если её нет
    os.makedirs("logs", exist_ok=True)
    
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                log_config = toml.load(f)
            logging.config.dictConfig(log_config)
            logging.info("Логирование успешно инициализировано.")
        except Exception as e:
            print(f"Ошибка при настройке логирования: {e}")
            logging.basicConfig(level=logging.INFO)
    else:
        print(f"Файл настройки логирования не найден: {config_path}. Используется базовая настройка.")
        logging.basicConfig(level=logging.INFO)

def load_main_config(config_path: str = "config/main.toml") -> dict:
    """Загрузка главного конфигурационного файла приложения."""
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Критическая ошибка: Главный конфиг {config_path} не найден.")
    
    with open(config_path, "r", encoding="utf-8") as f:
        return toml.load(f)