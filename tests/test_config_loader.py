import pytest
import os
import tempfile
import shutil
from pathlib import Path
import yaml
import toml

from src.utils.config_loader import (
    setup_logging,
    load_main_config,
    load_job_config,
    get_job_title
)


class TestSetupLogging:
    """Тесты для функции setup_logging."""
    
    def test_setup_logging_creates_logs_dir(self, temp_dir):
        """Проверяет, что функция создает папку logs."""
        logs_dir = os.path.join(temp_dir, "logs")
        
        # Меняем текущую директорию на временную
        original_cwd = os.getcwd()
        os.chdir(temp_dir)
        
        try:
            setup_logging()
            assert os.path.exists(logs_dir)
        finally:
            os.chdir(original_cwd)
    
    def test_setup_logging_with_missing_config(self, temp_dir):
        """Проверяет работу при отсутствии конфига логирования."""
        original_cwd = os.getcwd()
        os.chdir(temp_dir)
        
        try:
            # Не создаем config/logging.toml
            setup_logging()  # Не должно падать
        finally:
            os.chdir(original_cwd)
    
    def test_setup_logging_with_valid_config(self, temp_dir):
        """Проверяет работу с валидным конфигом."""
        original_cwd = os.getcwd()
        os.chdir(temp_dir)
        
        # Создаем папку config и конфиг
        config_dir = os.path.join(temp_dir, "config")
        os.makedirs(config_dir)
        
        log_config = {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "standard": {
                    "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
                }
            },
            "handlers": {
                "default": {
                    "level": "INFO",
                    "formatter": "standard",
                    "class": "logging.StreamHandler"
                }
            },
            "root": {
                "handlers": ["default"],
                "level": "INFO"
            }
        }
        
        log_config_path = os.path.join(config_dir, "logging.toml")
        with open(log_config_path, "w") as f:
            toml.dump(log_config, f)
        
        try:
            setup_logging()  # Не должно падать
        finally:
            os.chdir(original_cwd)


class TestLoadMainConfig:
    """Тесты для функции load_main_config."""
    
    def test_load_main_config_success(self, temp_dir):
        """Проверяет успешную загрузку конфига."""
        config_dir = os.path.join(temp_dir, "config")
        os.makedirs(config_dir)
        
        config_path = os.path.join(config_dir, "main.toml")
        test_config = {
            "database": {
                "test": {
                    "type": "sqlite",
                    "database": "test.db"
                }
            }
        }
        
        with open(config_path, "w") as f:
            toml.dump(test_config, f)
        
        result = load_main_config(config_path)
        assert result == test_config
    
    def test_load_main_config_file_not_found(self):
        """Проверяет исключение при отсутствии файла."""
        with pytest.raises(FileNotFoundError, match="Критическая ошибка"):
            load_main_config("nonexistent/config.toml")


class TestLoadJobConfig:
    """Тесты для функции load_job_config."""
    
    def test_load_job_config_success(self, temp_dir):
        """Проверяет успешную загрузку конфига отчета."""
        jobs_dir = os.path.join(temp_dir, "jobs")
        job_dir = os.path.join(jobs_dir, "test_job")
        os.makedirs(job_dir)
        
        config_path = os.path.join(job_dir, "config.yaml")
        test_config = {
            "title": "Test Job",
            "database_profile": "database.test",
            "enabled": True
        }
        
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(test_config, f)
        
        result = load_job_config("test_job", jobs_dir)
        assert result == test_config
    
    def test_load_job_config_file_not_found(self, temp_dir):
        """Проверяет возврат пустого словаря при отсутствии файла."""
        jobs_dir = os.path.join(temp_dir, "jobs")
        os.makedirs(jobs_dir)
        
        result = load_job_config("nonexistent_job", jobs_dir)
        assert result == {}
    
    def test_load_job_config_invalid_yaml(self, temp_dir):
        """Проверяет возврат пустого словаря при невалидном YAML."""
        jobs_dir = os.path.join(temp_dir, "jobs")
        job_dir = os.path.join(jobs_dir, "test_job")
        os.makedirs(job_dir)
        
        config_path = os.path.join(job_dir, "config.yaml")
        with open(config_path, "w", encoding="utf-8") as f:
            f.write("invalid: yaml: content: [")
        
        result = load_job_config("test_job", jobs_dir)
        assert result == {}
    
    def test_load_job_config_auto_path(self, temp_dir):
        """Проверяет автоматическое определение пути к jobs."""
        # Создаем структуру проекта
        src_dir = os.path.join(temp_dir, "src")
        jobs_dir = os.path.join(temp_dir, "jobs")
        job_dir = os.path.join(jobs_dir, "test_job")
        os.makedirs(job_dir)
        
        config_path = os.path.join(job_dir, "config.yaml")
        test_config = {"title": "Auto Path Test"}
        
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(test_config, f)
        
        original_cwd = os.getcwd()
        os.chdir(src_dir)
        
        try:
            result = load_job_config("test_job")  # Без явного указания jobs_dir
            assert result == test_config
        finally:
            os.chdir(original_cwd)
    
    def test_load_job_config_empty_yaml(self, temp_dir):
        """Проверяет возврат пустого словаря для пустого YAML."""
        jobs_dir = os.path.join(temp_dir, "jobs")
        job_dir = os.path.join(jobs_dir, "test_job")
        os.makedirs(job_dir)
        
        config_path = os.path.join(job_dir, "config.yaml")
        with open(config_path, "w", encoding="utf-8") as f:
            f.write("")
        
        result = load_job_config("test_job", jobs_dir)
        assert result == {}


class TestGetJobTitle:
    """Тесты для функции get_job_title."""
    
    def test_get_job_title_with_title(self, temp_dir):
        """Проверяет получение заголовка из конфига."""
        jobs_dir = os.path.join(temp_dir, "jobs")
        job_dir = os.path.join(jobs_dir, "test_job")
        os.makedirs(job_dir)
        
        config_path = os.path.join(job_dir, "config.yaml")
        test_config = {"title": "Custom Title"}
        
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(test_config, f)
        
        result = get_job_title("test_job", jobs_dir)
        assert result == "Custom Title"
    
    def test_get_job_title_without_title(self, temp_dir):
        """Проверяет возврат имени задачи при отсутствии заголовка."""
        jobs_dir = os.path.join(temp_dir, "jobs")
        job_dir = os.path.join(jobs_dir, "test_job")
        os.makedirs(job_dir)
        
        config_path = os.path.join(job_dir, "config.yaml")
        test_config = {"database_profile": "database.test"}
        
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(test_config, f)
        
        result = get_job_title("test_job", jobs_dir)
        assert result == "test_job"
    
    def test_get_job_title_missing_config(self, temp_dir):
        """Проверяет возврат имени задачи при отсутствии конфига."""
        jobs_dir = os.path.join(temp_dir, "jobs")
        os.makedirs(jobs_dir)
        
        result = get_job_title("nonexistent_job", jobs_dir)
        assert result == "nonexistent_job"
