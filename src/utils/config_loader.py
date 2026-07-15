import os
import toml
import yaml
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

def load_job_config(job_name: str, jobs_dir: str = None) -> dict:
    """Загрузка конфигурационного файла конкретного отчета.
    
    Args:
        job_name: Имя папки с отчетом
        jobs_dir: Путь к папке с отчетами (по умолчанию определяется автоматически)
    
    Returns:
        Словарь с конфигурацией отчета или пустой словарь при ошибке
    """
    if jobs_dir is None:
        # Определяем путь к jobs автоматически
        current_dir = os.path.dirname(os.path.abspath(__file__))
        if os.path.basename(current_dir) == "src":
            base_dir = os.path.dirname(current_dir)
        else:
            base_dir = current_dir
        jobs_dir = os.path.join(base_dir, "jobs")
    
    yaml_path = os.path.join(jobs_dir, job_name, "config.yaml")
    
    if not os.path.exists(yaml_path):
        return {}
    
    try:
        with open(yaml_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        logging.warning(f"Не удалось прочитать config.yaml для {job_name}: {e}")
        return {}

def get_job_title(job_name: str, jobs_dir: str = None) -> str:
    """Получает заголовок отчета из config.yaml.
    
    Args:
        job_name: Имя папки с отчетом
        jobs_dir: Путь к папке с отчетами (по умолчанию определяется автоматически)
    
    Returns:
        Заголовок отчета или job_name, если заголовок не найден
    """
    config = load_job_config(job_name, jobs_dir)
    return config.get("title", job_name)