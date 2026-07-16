import pytest
import os
import tempfile
import sqlite3
from pathlib import Path

from src.utils.db_logger import (
    init_history_db,
    log_job_state,
    log_user_run
)


class TestInitHistoryDb:
    """Тесты для функции init_history_db."""
    
    def test_init_history_db_creates_tables(self, temp_dir):
        """Проверяет создание таблиц в БД."""
        # Переопределяем путь к БД для теста
        test_db_path = os.path.join(temp_dir, "test_history.db")
        
        original_db_path = None
        try:
            # Сохраняем оригинальный путь
            import src.utils.db_logger as db_logger_module
            original_db_path = db_logger_module.DB_PATH
            db_logger_module.DB_PATH = test_db_path
            
            init_history_db()
            
            # Проверяем, что файл БД создан
            assert os.path.exists(test_db_path)
            
            # Проверяем наличие таблиц
            conn = sqlite3.connect(test_db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            assert "job_states" in tables
            assert "user_run_history" in tables
            
            conn.close()
        finally:
            # Восстанавливаем оригинальный путь
            if original_db_path:
                db_logger_module.DB_PATH = original_db_path
    
    def test_init_history_db_idempotent(self, temp_dir):
        """Проверяет, что повторный вызов не вызывает ошибок."""
        test_db_path = os.path.join(temp_dir, "test_history.db")
        
        import src.utils.db_logger as db_logger_module
        original_db_path = db_logger_module.DB_PATH
        db_logger_module.DB_PATH = test_db_path
        
        try:
            init_history_db()
            init_history_db()  # Второй вызов не должен падать
            
            assert os.path.exists(test_db_path)
        finally:
            db_logger_module.DB_PATH = original_db_path


class TestLogJobState:
    """Тесты для функции log_job_state."""
    
    def test_log_job_state_insert(self, temp_dir):
        """Проверяет вставку записи о состоянии задачи."""
        test_db_path = os.path.join(temp_dir, "test_history.db")
        
        import src.utils.db_logger as db_logger_module
        original_db_path = db_logger_module.DB_PATH
        db_logger_module.DB_PATH = test_db_path
        
        try:
            log_job_state("test_job", "success", "No error")
            
            conn = sqlite3.connect(test_db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT job_name, status, error_message FROM job_states WHERE job_name = ?", ("test_job",))
            row = cursor.fetchone()
            
            assert row is not None
            assert row[0] == "test_job"
            assert row[1] == "success"
            assert row[2] == "No error"
            
            conn.close()
        finally:
            db_logger_module.DB_PATH = original_db_path
    
    def test_log_job_state_update(self, temp_dir):
        """Проверяет обновление существующей записи (UPSERT)."""
        test_db_path = os.path.join(temp_dir, "test_history.db")
        
        import src.utils.db_logger as db_logger_module
        original_db_path = db_logger_module.DB_PATH
        db_logger_module.DB_PATH = test_db_path
        
        try:
            # Первая вставка
            log_job_state("test_job", "started", "")
            
            # Обновление
            log_job_state("test_job", "success", "")
            
            conn = sqlite3.connect(test_db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM job_states WHERE job_name = ?", ("test_job",))
            count = cursor.fetchone()[0]
            
            assert count == 1  # Должна быть только одна запись
            
            cursor.execute("SELECT status FROM job_states WHERE job_name = ?", ("test_job",))
            status = cursor.fetchone()[0]
            
            assert status == "success"  # Статус должен быть обновлен
            
            conn.close()
        finally:
            db_logger_module.DB_PATH = original_db_path
    
    def test_log_job_state_with_error(self, temp_dir):
        """Проверяет запись с ошибкой."""
        test_db_path = os.path.join(temp_dir, "test_history.db")
        
        import src.utils.db_logger as db_logger_module
        original_db_path = db_logger_module.DB_PATH
        db_logger_module.DB_PATH = test_db_path
        
        try:
            error_msg = "Connection timeout"
            log_job_state("test_job", "error", error_msg)
            
            conn = sqlite3.connect(test_db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT error_message FROM job_states WHERE job_name = ?", ("test_job",))
            row = cursor.fetchone()
            
            assert row[0] == error_msg
            
            conn.close()
        finally:
            db_logger_module.DB_PATH = original_db_path


class TestLogUserRun:
    """Тесты для функции log_user_run."""
    
    def test_log_user_run_insert(self, temp_dir):
        """Проверяет вставку записи о запуске пользователем."""
        test_db_path = os.path.join(temp_dir, "test_history.db")
        
        import src.utils.db_logger as db_logger_module
        original_db_path = db_logger_module.DB_PATH
        db_logger_module.DB_PATH = test_db_path
        
        try:
            params = {"start_date": "2024-01-01", "end_date": "2024-12-31"}
            log_user_run(
                user_id="12345",
                user_name="Test User",
                job_name="test_job",
                job_title="Test Job Title",
                status="success",
                parameters=params,
                error_message=""
            )
            
            conn = sqlite3.connect(test_db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT user_id, user_name, job_name, job_title, status FROM user_run_history WHERE user_id = ?",
                ("12345",)
            )
            row = cursor.fetchone()
            
            assert row is not None
            assert row[0] == "12345"
            assert row[1] == "Test User"
            assert row[2] == "test_job"
            assert row[3] == "Test Job Title"
            assert row[4] == "success"
            
            conn.close()
        finally:
            db_logger_module.DB_PATH = original_db_path
    
    def test_log_user_run_with_parameters(self, temp_dir):
        """Проверяет сериализацию параметров в JSON."""
        test_db_path = os.path.join(temp_dir, "test_history.db")
        
        import src.utils.db_logger as db_logger_module
        original_db_path = db_logger_module.DB_PATH
        db_logger_module.DB_PATH = test_db_path
        
        try:
            params = {"date": "2024-01-01", "ids": [1, 2, 3]}
            log_user_run(
                user_id="12345",
                user_name="Test User",
                job_name="test_job",
                job_title="Test Job",
                status="started",
                parameters=params
            )
            
            conn = sqlite3.connect(test_db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT parameters FROM user_run_history WHERE user_id = ?", ("12345",))
            row = cursor.fetchone()
            
            assert row is not None
            
            # Проверяем, что это валидный JSON
            import json
            parsed_params = json.loads(row[0])
            assert parsed_params == params
            
            conn.close()
        finally:
            db_logger_module.DB_PATH = original_db_path
    
    def test_log_user_run_without_parameters(self, temp_dir):
        """Проверяет запись без параметров."""
        test_db_path = os.path.join(temp_dir, "test_history.db")
        
        import src.utils.db_logger as db_logger_module
        original_db_path = db_logger_module.DB_PATH
        db_logger_module.DB_PATH = test_db_path
        
        try:
            log_user_run(
                user_id="12345",
                user_name="Test User",
                job_name="test_job",
                job_title="Test Job",
                status="success"
            )
            
            conn = sqlite3.connect(test_db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT parameters FROM user_run_history WHERE user_id = ?", ("12345",))
            row = cursor.fetchone()
            
            assert row is not None
            
            import json
            parsed_params = json.loads(row[0])
            assert parsed_params == {}
            
            conn.close()
        finally:
            db_logger_module.DB_PATH = original_db_path
    
    def test_log_user_run_with_error(self, temp_dir):
        """Проверяет запись с ошибкой."""
        test_db_path = os.path.join(temp_dir, "test_history.db")
        
        import src.utils.db_logger as db_logger_module
        original_db_path = db_logger_module.DB_PATH
        db_logger_module.DB_PATH = test_db_path
        
        try:
            error_msg = "Database connection failed"
            log_user_run(
                user_id="12345",
                user_name="Test User",
                job_name="test_job",
                job_title="Test Job",
                status="error",
                error_message=error_msg
            )
            
            conn = sqlite3.connect(test_db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT error_message FROM user_run_history WHERE user_id = ?", ("12345",))
            row = cursor.fetchone()
            
            assert row[0] == error_msg
            
            conn.close()
        finally:
            db_logger_module.DB_PATH = original_db_path
    
    def test_log_user_run_multiple_records(self, temp_dir):
        """Проверяет создание нескольких записей."""
        test_db_path = os.path.join(temp_dir, "test_history.db")
        
        import src.utils.db_logger as db_logger_module
        original_db_path = db_logger_module.DB_PATH
        db_logger_module.DB_PATH = test_db_path
        
        try:
            # Первый запуск
            log_user_run("12345", "Test User", "test_job", "Test Job", "started")
            
            # Второй запуск
            log_user_run("12345", "Test User", "test_job", "Test Job", "success")
            
            conn = sqlite3.connect(test_db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM user_run_history WHERE user_id = ?", ("12345",))
            count = cursor.fetchone()[0]
            
            assert count == 2  # Должны быть две записи
            
            conn.close()
        finally:
            db_logger_module.DB_PATH = original_db_path
