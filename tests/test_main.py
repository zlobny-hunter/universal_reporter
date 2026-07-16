import pytest
import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import toml
import yaml

from src.main import (
    get_connection_for_job,
    get_all_jobs,
    handle_delivery
)


class TestGetAllJobs:
    """Тесты для функции get_all_jobs."""
    
    def test_get_all_jobs_success(self, temp_dir):
        """Проверяет успешное получение списка отчетов."""
        jobs_dir = os.path.join(temp_dir, "jobs")
        
        # Создаем несколько отчетов
        for job_name in ["job1", "job2", "job3"]:
            job_dir = os.path.join(jobs_dir, job_name)
            os.makedirs(job_dir)
            
            config_path = os.path.join(job_dir, "config.yaml")
            config = {"title": f"Job {job_name}", "enabled": True}
            
            with open(config_path, "w", encoding="utf-8") as f:
                yaml.dump(config, f)
        
        # Создаем отчет, который отключен
        disabled_job_dir = os.path.join(jobs_dir, "disabled_job")
        os.makedirs(disabled_job_dir)
        disabled_config_path = os.path.join(disabled_job_dir, "config.yaml")
        disabled_config = {"title": "Disabled Job", "enabled": False}
        
        with open(disabled_config_path, "w", encoding="utf-8") as f:
            yaml.dump(disabled_config, f)
        
        # Создаем папку без config.yaml
        no_config_dir = os.path.join(jobs_dir, "no_config")
        os.makedirs(no_config_dir)
        
        # Мокаем JOBS_DIR
        with patch('src.main.JOBS_DIR', jobs_dir):
            jobs = get_all_jobs()
            
            assert len(jobs) == 3
            assert "job1" in jobs
            assert "job2" in jobs
            assert "job3" in jobs
            assert "disabled_job" not in jobs
            assert "no_config" not in jobs
    
    def test_get_all_jobs_empty_directory(self, temp_dir):
        """Проверяет возврат пустого списка при отсутствии отчетов."""
        jobs_dir = os.path.join(temp_dir, "jobs")
        os.makedirs(jobs_dir)
        
        with patch('src.main.JOBS_DIR', jobs_dir):
            jobs = get_all_jobs()
            assert jobs == []
    
    def test_get_all_jobs_no_jobs_directory(self, temp_dir):
        """Проверяет возврат пустого списка при отсутствии папки jobs."""
        jobs_dir = os.path.join(temp_dir, "nonexistent_jobs")
        
        with patch('src.main.JOBS_DIR', jobs_dir):
            jobs = get_all_jobs()
            assert jobs == []


class TestGetConnectionForJob:
    """Тесты для функции get_connection_for_job."""
    
    def test_get_connection_sqlite(self, temp_dir):
        """Проверяет подключение к SQLite."""
        # Создаем структуру конфигов
        config_dir = os.path.join(temp_dir, "config")
        os.makedirs(config_dir)
        
        jobs_dir = os.path.join(temp_dir, "jobs")
        job_dir = os.path.join(jobs_dir, "test_job")
        os.makedirs(job_dir)
        
        # Создаем main.toml
        main_config = {
            "database": {
                "sqlite_test": {
                    "type": "sqlite",
                    "database": ":memory:"
                }
            }
        }
        
        main_config_path = os.path.join(config_dir, "main.toml")
        with open(main_config_path, "w") as f:
            toml.dump(main_config, f)
        
        # Создаем config.yaml для отчета
        job_config = {
            "title": "Test Job",
            "database_profile": "sqlite_test"
        }
        
        job_config_path = os.path.join(job_dir, "config.yaml")
        with open(job_config_path, "w", encoding="utf-8") as f:
            yaml.dump(job_config, f)
        
        # Мокаем пути
        with patch('src.main.MAIN_CONFIG_PATH', main_config_path), \
             patch('src.main.JOBS_DIR', jobs_dir):
            
            conn, tunnel = get_connection_for_job("test_job")
            
            assert conn is not None
            assert tunnel is None
            conn.close()
    
    def test_get_connection_missing_main_config(self, temp_dir):
        """Проверяет исключение при отсутствии main.toml."""
        jobs_dir = os.path.join(temp_dir, "jobs")
        job_dir = os.path.join(jobs_dir, "test_job")
        os.makedirs(job_dir)
        
        job_config = {"database_profile": "sqlite_test"}
        job_config_path = os.path.join(job_dir, "config.yaml")
        with open(job_config_path, "w", encoding="utf-8") as f:
            yaml.dump(job_config, f)
        
        with patch('src.main.MAIN_CONFIG_PATH', "nonexistent/config.toml"), \
             patch('src.main.JOBS_DIR', jobs_dir):
            
            with pytest.raises(FileNotFoundError, match="Критическая ошибка"):
                get_connection_for_job("test_job")
    
    def test_get_connection_missing_job_config(self, temp_dir):
        """Проверяет исключение при отсутствии config.yaml отчета."""
        config_dir = os.path.join(temp_dir, "config")
        os.makedirs(config_dir)
        
        jobs_dir = os.path.join(temp_dir, "jobs")
        os.makedirs(jobs_dir)
        
        main_config = {"database": {"sqlite_test": {"type": "sqlite"}}}
        main_config_path = os.path.join(config_dir, "main.toml")
        with open(main_config_path, "w") as f:
            toml.dump(main_config, f)
        
        with patch('src.main.MAIN_CONFIG_PATH', main_config_path), \
             patch('src.main.JOBS_DIR', jobs_dir):
            
            with pytest.raises(FileNotFoundError, match="Конфигурационный файл"):
                get_connection_for_job("nonexistent_job")
    
    def test_get_connection_missing_database_profile(self, temp_dir):
        """Проверяет исключение при отсутствии database_profile."""
        config_dir = os.path.join(temp_dir, "config")
        os.makedirs(config_dir)
        
        jobs_dir = os.path.join(temp_dir, "jobs")
        job_dir = os.path.join(jobs_dir, "test_job")
        os.makedirs(job_dir)
        
        main_config = {"database": {"sqlite_test": {"type": "sqlite"}}}
        main_config_path = os.path.join(config_dir, "main.toml")
        with open(main_config_path, "w") as f:
            toml.dump(main_config, f)
        
        job_config = {"title": "Test Job"}  # Без database_profile
        job_config_path = os.path.join(job_dir, "config.yaml")
        with open(job_config_path, "w", encoding="utf-8") as f:
            yaml.dump(job_config, f)
        
        with patch('src.main.MAIN_CONFIG_PATH', main_config_path), \
             patch('src.main.JOBS_DIR', jobs_dir):
            
            with pytest.raises(ValueError, match="не содержит поле database_profile"):
                get_connection_for_job("test_job")
    
    def test_get_connection_invalid_db_profile(self, temp_dir):
        """Проверяет исключение при неверном профиле БД."""
        config_dir = os.path.join(temp_dir, "config")
        os.makedirs(config_dir)
        
        jobs_dir = os.path.join(temp_dir, "jobs")
        job_dir = os.path.join(jobs_dir, "test_job")
        os.makedirs(job_dir)
        
        main_config = {"database": {"sqlite_test": {"type": "sqlite"}}}
        main_config_path = os.path.join(config_dir, "main.toml")
        with open(main_config_path, "w") as f:
            toml.dump(main_config, f)
        
        job_config = {"database_profile": "nonexistent_profile"}
        job_config_path = os.path.join(job_dir, "config.yaml")
        with open(job_config_path, "w", encoding="utf-8") as f:
            yaml.dump(job_config, f)
        
        with patch('src.main.MAIN_CONFIG_PATH', main_config_path), \
             patch('src.main.JOBS_DIR', jobs_dir):
            
            with pytest.raises(ValueError, match="не найдена или некорректна"):
                get_connection_for_job("test_job")
    
    def test_get_connection_unsupported_db_type(self, temp_dir):
        """Проверяет исключение для неподдерживаемого типа БД."""
        config_dir = os.path.join(temp_dir, "config")
        os.makedirs(config_dir)
        
        jobs_dir = os.path.join(temp_dir, "jobs")
        job_dir = os.path.join(jobs_dir, "test_job")
        os.makedirs(job_dir)
        
        main_config = {
            "database": {
                "unsupported_db": {
                    "type": "oracle"
                }
            }
        }
        main_config_path = os.path.join(config_dir, "main.toml")
        with open(main_config_path, "w") as f:
            toml.dump(main_config, f)
        
        job_config = {"database_profile": "unsupported_db"}
        job_config_path = os.path.join(job_dir, "config.yaml")
        with open(job_config_path, "w", encoding="utf-8") as f:
            yaml.dump(job_config, f)
        
        with patch('src.main.MAIN_CONFIG_PATH', main_config_path), \
             patch('src.main.JOBS_DIR', jobs_dir):
            
            with pytest.raises(ValueError, match="Неподдерживаемый тип СУБД"):
                get_connection_for_job("test_job")


class TestHandleDelivery:
    """Тесты для функции handle_delivery."""
    
    def test_handle_delivery_no_delivery_section(self, temp_dir):
        """Проверяет возврат при отсутствии секции delivery."""
        job_config = {"title": "Test Job"}
        test_file = os.path.join(temp_dir, "test.xlsx")
        
        with open(test_file, "w") as f:
            f.write("test")
        
        # Функция не должна падать
        handle_delivery(job_config, test_file)
    
    def test_handle_delivery_local_copy(self, temp_dir):
        """Проверяет локальное копирование файла."""
        target_dir = os.path.join(temp_dir, "archive")
        os.makedirs(target_dir)
        
        job_config = {
            "delivery": {
                "local": {
                    "enabled": True,
                    "target_path": target_dir
                }
            }
        }
        
        test_file = os.path.join(temp_dir, "test.xlsx")
        with open(test_file, "w") as f:
            f.write("test content")
        
        handle_delivery(job_config, test_file)
        
        # Проверяем, что файл скопирован
        copied_file = os.path.join(target_dir, "test.xlsx")
        assert os.path.exists(copied_file)
        
        with open(copied_file, "r") as f:
            assert f.read() == "test content"
    
    def test_handle_delivery_local_disabled(self, temp_dir):
        """Проверяет, что локальное копирование не выполняется при disabled."""
        job_config = {
            "delivery": {
                "local": {
                    "enabled": False,
                    "target_path": os.path.join(temp_dir, "archive")
                }
            }
        }
        
        test_file = os.path.join(temp_dir, "test.xlsx")
        with open(test_file, "w") as f:
            f.write("test")
        
        handle_delivery(job_config, test_file)
        
        # Проверяем, что файл не скопирован
        archive_dir = os.path.join(temp_dir, "archive")
        assert not os.path.exists(archive_dir)
    
    @patch('src.main.toml.load')
    def test_handle_delivery_nextcloud_missing_config(self, mock_toml_load, temp_dir):
        """Проверяет обработку отсутствующего конфига Nextcloud."""
        job_config = {
            "delivery": {
                "nextcloud": {
                    "enabled": True,
                    "profile": "test_profile"
                }
            }
        }
        
        test_file = os.path.join(temp_dir, "test.xlsx")
        with open(test_file, "w") as f:
            f.write("test")
        
        # Мокаем загрузку конфига с отсутствующим профилем
        mock_toml_load.return_value = {
            "delivery": {
                "nextcloud": {}
            }
        }
        
        # Функция не должна падать
        handle_delivery(job_config, test_file)
    
    @patch('src.main.toml.load')
    def test_handle_delivery_mail_enabled(self, mock_toml_load, temp_dir):
        """Проверяет логирование при включенной почтовой рассылке."""
        job_config = {
            "delivery": {
                "mail": {
                    "enabled": True
                }
            }
        }
        
        test_file = os.path.join(temp_dir, "test.xlsx")
        with open(test_file, "w") as f:
            f.write("test")
        
        # Функция не должна падать
        handle_delivery(job_config, test_file)
