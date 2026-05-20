import logging
from datetime import datetime
import pandas as pd
from sqlalchemy import create_engine, text

logger = logging.getLogger("DBClient")

class DBClient:
    def __init__(self, db_config: dict):
        """
        Инициализация подключения к БД на основе переданного конфига.
        """
        self.config = db_config
        self.engine = self._create_engine_instance()

    def _create_engine_instance(self):
        """Формирует строку подключения и создает движок SQLAlchemy."""
        dialect = self.config.get("dialect", "sqlite")
        
        if dialect == "sqlite":
            logger.info("Используется тестовая база данных SQLite в памяти (In-Memory).")
            return create_engine("sqlite:///:memory:")
        
        # Сборка строки для полноценных СУБД: postgresql, mysql, mariadb и т.д.
        user = self.config.get("username")
        password = self.config.get("password")
        host = self.config.get("host")
        port = self.config.get("port")
        db_name = self.config.get("database")
        
        connection_url = f"{dialect}://{user}:{password}@{host}:{port}/{db_name}"
        logger.info(f"Инициализация подключения к БД: {dialect}://{host}:{port}/{db_name}")
        return create_engine(connection_url)

    def execute_sql_file(self, file_path: str, params: dict = None) -> pd.DataFrame:
        """
        Читает SQL-файл и выполняет запрос, безопасно подставляя переданные параметры.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"SQL-файл не найден по пути: {file_path}")
            
        with open(file_path, 'r', encoding='utf-8') as f:
            sql_query = f.read()
            
        # Если параметры не переданы, инициализируем пустой словарь
        if params is None:
            params = {}
            
        logger.debug(f"Выполнение SQL из файла {file_path} с параметрами: {params}")
        
        # Передаем params в pandas. read_sql автоматически применит безопасный binding параметров
        df = pd.read_sql(sql_query, self.engine, params=params)
        return df