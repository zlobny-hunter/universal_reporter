import pytest
import os
import tempfile
import shutil
from pathlib import Path

# Настройка пути к проекту для импортов
import sys
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@pytest.fixture
def temp_dir():
    """Создает временную директорию для тестов и удаляет её после."""
    temp_path = tempfile.mkdtemp()
    yield temp_path
    shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def sample_job_config():
    """Пример конфигурации отчета."""
    return {
        "title": "Test Report",
        "description": "Test description",
        "database_profile": "database.sqlite_test",
        "enabled": True,
        "parameters": {
            "start_date": {
                "type": "date",
                "label": "Start Date",
                "default": "2024-01-01"
            },
            "end_date": {
                "type": "date",
                "label": "End Date",
                "default": "2024-12-31"
            }
        },
        "require_parameters": False,
        "delivery": {
            "send_to_chat": True,
            "nextcloud": {
                "enabled": False
            }
        }
    }


@pytest.fixture
def sample_main_config():
    """Пример главного конфигурационного файла."""
    return {
        "database": {
            "sqlite_test": {
                "type": "sqlite",
                "database": "data/test.db"
            },
            "postgres_prod": {
                "type": "postgres",
                "host": "localhost",
                "port": 5432,
                "user": "test_user",
                "password": "test_pass",
                "database": "test_db"
            }
        },
        "delivery": {
            "yandex_messenger": {
                "bot_token": "test_token",
                "bot_username": "test_bot"
            }
        }
    }


@pytest.fixture
def sample_sql_file(temp_dir):
    """Создает тестовый SQL файл."""
    sql_content = """
    SELECT 
        :param1 as column1,
        :param2 as column2
    """
    sql_path = os.path.join(temp_dir, "test_query.sql")
    with open(sql_path, "w", encoding="utf-8") as f:
        f.write(sql_content)
    return sql_path
