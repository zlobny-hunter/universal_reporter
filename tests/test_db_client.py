import pytest
import os
import tempfile
import pandas as pd
from unittest.mock import Mock, patch, MagicMock

from src.database.db_client import DBClient


class TestDBClientInit:
    """Тесты для инициализации DBClient."""
    
    def test_init_sqlite(self):
        """Проверяет инициализацию для SQLite."""
        config = {
            "dialect": "sqlite",
            "database": "test.db"
        }
        
        client = DBClient(config)
        
        assert client.dialect == "sqlite"
        assert client.database == "test.db"
        assert client.engine is not None
    
    def test_init_postgres(self):
        """Проверяет инициализацию для PostgreSQL."""
        config = {
            "dialect": "postgres",
            "host": "localhost",
            "port": 5432,
            "user": "test_user",
            "password": "test_pass",
            "database": "test_db"
        }
        
        client = DBClient(config)
        
        assert client.dialect == "postgres"
        assert client.host == "localhost"
        assert client.port == 5432
        assert client.user == "test_user"
        assert client.password == "test_pass"
        assert client.database == "test_db"
    
    def test_init_default_values(self):
        """Проверяет значения по умолчанию."""
        config = {
            "dialect": "sqlite"
        }
        
        client = DBClient(config)
        
        assert client.dialect == "sqlite"
        assert client.host == "localhost"
        assert client.user == ""
        assert client.password == ""
        assert client.database == ""
    
    def test_init_port_parsing_string_none(self):
        """Проверяет парсинг порта из строки 'None'."""
        config = {
            "dialect": "postgres",
            "port": "None"
        }
        
        client = DBClient(config)
        
        assert client.port == 5432  # Default for postgres
    
    def test_init_port_parsing_empty_string(self):
        """Проверяет парсинг пустого порта."""
        config = {
            "dialect": "postgres",
            "port": ""
        }
        
        client = DBClient(config)
        
        assert client.port == 5432
    
    def test_init_port_parsing_valid(self):
        """Проверяет парсинг валидного порта."""
        config = {
            "dialect": "postgres",
            "port": "3306"
        }
        
        client = DBClient(config)
        
        assert client.port == 3306
    
    def test_init_mysql_default_port(self):
        """Проверяет порт по умолчанию для MySQL."""
        config = {
            "dialect": "mysql",
            "port": "None"
        }
        
        client = DBClient(config)
        
        assert client.port == 3306  # Default for mysql


class TestDBClientExecuteSqlFile:
    """Тесты для метода execute_sql_file."""
    
    def test_execute_sql_file_success(self, sample_sql_file):
        """Проверяет успешное выполнение SQL файла."""
        config = {
            "dialect": "sqlite",
            "database": ":memory:"
        }
        
        client = DBClient(config)
        
        # Создаем тестовую таблицу
        with client.engine.connect() as conn:
            conn.execute("CREATE TABLE test (col1 TEXT, col2 TEXT)")
        
        result = client.execute_sql_file(sample_sql_file, params={"param1": "value1", "param2": "value2"})
        
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 1
        assert result.columns.tolist() == ["column1", "column2"]
    
    def test_execute_sql_file_not_found(self):
        """Проверяет исключение при отсутствии файла."""
        config = {
            "dialect": "sqlite",
            "database": ":memory:"
        }
        
        client = DBClient(config)
        
        with pytest.raises(FileNotFoundError, match="SQL-файл не найден"):
            client.execute_sql_file("nonexistent.sql")
    
    def test_execute_sql_file_without_params(self, sample_sql_file):
        """Проверяет выполнение без параметров."""
        config = {
            "dialect": "sqlite",
            "database": ":memory:"
        }
        
        client = DBClient(config)
        
        # Создаем тестовую таблицу
        with client.engine.connect() as conn:
            conn.execute("CREATE TABLE test (col1 TEXT, col2 TEXT)")
        
        result = client.execute_sql_file(sample_sql_file)
        
        assert isinstance(result, pd.DataFrame)
    
    def test_execute_sql_file_empty_params(self, sample_sql_file):
        """Проверяет выполнение с пустым словарем параметров."""
        config = {
            "dialect": "sqlite",
            "database": ":memory:"
        }
        
        client = DBClient(config)
        
        # Создаем тестовую таблицу
        with client.engine.connect() as conn:
            conn.execute("CREATE TABLE test (col1 TEXT, col2 TEXT)")
        
        result = client.execute_sql_file(sample_sql_file, params={})
        
        assert isinstance(result, pd.DataFrame)
    
    def test_execute_sql_file_with_complex_query(self, temp_dir):
        """Проверяет выполнение сложного SQL запроса."""
        config = {
            "dialect": "sqlite",
            "database": ":memory:"
        }
        
        client = DBClient(config)
        
        # Создаем тестовую таблицу с данными
        with client.engine.connect() as conn:
            conn.execute("CREATE TABLE users (id INTEGER, name TEXT, age INTEGER)")
            conn.execute("INSERT INTO users VALUES (1, 'Alice', 30)")
            conn.execute("INSERT INTO users VALUES (2, 'Bob', 25)")
        
        # Создаем SQL файл с запросом
        sql_content = """
        SELECT 
            id,
            name,
            age
        FROM users
        WHERE age > :min_age
        """
        sql_path = os.path.join(temp_dir, "complex_query.sql")
        with open(sql_path, "w", encoding="utf-8") as f:
            f.write(sql_content)
        
        result = client.execute_sql_file(sql_path, params={"min_age": 28})
        
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 1
        assert result.iloc[0]["name"] == "Alice"
    
    def test_execute_sql_file_encoding(self, temp_dir):
        """Проверяет чтение SQL файла с UTF-8 кодировкой."""
        config = {
            "dialect": "sqlite",
            "database": ":memory:"
        }
        
        client = DBClient(config)
        
        # Создаем SQL файл с кириллицей
        sql_content = """
        SELECT 
            :параметр1 as колонка1,
            :параметр2 as колонка2
        """
        sql_path = os.path.join(temp_dir, "unicode_query.sql")
        with open(sql_path, "w", encoding="utf-8") as f:
            f.write(sql_content)
        
        # Создаем тестовую таблицу
        with client.engine.connect() as conn:
            conn.execute("CREATE TABLE test (колонка1 TEXT, колонка2 TEXT)")
        
        result = client.execute_sql_file(sql_path, params={"параметр1": "значение1", "параметр2": "значение2"})
        
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 1


class TestDBClientEngineCreation:
    """Тесты для создания engine."""
    
    def test_sqlite_engine_url(self):
        """Проверяет правильность URL для SQLite."""
        config = {
            "dialect": "sqlite",
            "database": "test.db"
        }
        
        client = DBClient(config)
        
        expected_url = "sqlite:///test.db"
        assert str(client.engine.url) == expected_url
    
    def test_postgres_engine_url(self):
        """Проверяет правильность URL для PostgreSQL."""
        config = {
            "dialect": "postgres",
            "host": "localhost",
            "port": 5432,
            "user": "testuser",
            "password": "testpass",
            "database": "testdb"
        }
        
        client = DBClient(config)
        
        url_str = str(client.engine.url)
        assert "postgresql://testuser:testpass@localhost:5432/testdb" == url_str
    
    def test_case_insensitive_dialect(self):
        """Проверяет регистронезависимость dialect."""
        config = {
            "dialect": "PostgreSQL",  # В верхнем регистре
            "host": "localhost",
            "port": 5432,
            "user": "testuser",
            "password": "testpass",
            "database": "testdb"
        }
        
        client = DBClient(config)
        
        assert client.dialect == "postgresql"
