import os
import yaml
import logging
import sqlite3
from datetime import datetime, timedelta
import sqlalchemy as sa
from sshtunnel import SSHTunnelForwarder
import pandas as pd
import tomllib
import paramiko
# Заплатка для совместимости новых версий paramiko и старых sshtunnel
if not hasattr(paramiko, 'DSSKey'):
    class DummyDSSKey:
        pass
    paramiko.DSSKey = DummyDSSKey

# Предполагаем, что ваши внутренние модули называются так.
# Если пути к db_client или writer отличаются — скорректируйте эти импорты.
from src.database.db_client import DBClient
from src.excel.writer import build_excel_workbook

logger = logging.getLogger("Core.Orchestrator")

# Глобальный путь к лог-базе состояний (чтобы Streamlit видел историю запусков)
DB_STATUS_PATH = "data/job_status.db"


def get_all_jobs() -> list:
    """Возвращает список всех папок-отчетов из директории jobs."""
    jobs_dir = "jobs"
    if not os.path.exists(jobs_dir):
        return []
    return [d for d in os.listdir(jobs_dir) if os.path.isdir(os.path.join(jobs_dir, d))]


def log_job_state(job_name: str, status: str, error_msg: str = "", job_title: str = ""):
    """Записывает результат выполнения отчета в системную БД SQLite для UI."""
    target_db_path = os.path.join(os.getcwd(), "data", "job_status.db")
    os.makedirs(os.path.dirname(target_db_path), exist_ok=True)

    conn = sqlite3.connect(target_db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS job_runs
                       (
                           id INTEGER PRIMARY KEY AUTOINCREMENT,
                           job_name TEXT,
                           job_title TEXT,  -- <--- ДОБАВИЛИ КОЛОНКУ
                           run_time TEXT,
                           status TEXT,
                           error_message TEXT
                       )
                       """)
        # На случай, если таблица уже существовала без этого поля, добавим его программно
        try:
            cursor.execute("ALTER TABLE job_runs ADD COLUMN job_title TEXT")
        except sqlite3.OperationalError:
            pass  # Колонка уже существует, всё ок

        cursor.execute(
            "INSERT INTO job_runs (job_name, job_title, run_time, status, error_message) VALUES (?, ?, ?, ?, ?)",
            (job_name, job_title, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), status, error_msg)
        )
        conn.commit()
    except Exception as e:
        print(f"[ERROR log_job_state] Ошибка записи в SQLite: {e}")
    finally:
        conn.close()


def calculate_default_params(param_declaration: dict) -> dict:
    """Вычисляет дефолтные значения параметров для автоматического запуска по шедулеру."""
    computed = {}
    for p_name, p_info in param_declaration.items():
        p_type = p_info.get("type")
        default_val = p_info.get("default")

        if default_val == "None" or default_val is None:
            computed[p_name] = None
            continue

        if p_type == "date":
            if default_val == "today":
                computed[p_name] = datetime.now().strftime("%Y-%m-%d 23:59:59")
            elif default_val == "minus_7_days":
                minus_7 = datetime.now() - timedelta(days=7)
                computed[p_name] = minus_7.strftime("%Y-%m-%d 00:00:00")
            else:
                computed[p_name] = default_val

        elif p_type == "int_list":
            if isinstance(default_val, list):
                clean_list = []
                for x in default_val:
                    if x is not None and str(x).strip() != "" and str(x).lower() != "none":
                        clean_list.append(int(x))
                computed[p_name] = tuple(clean_list) if clean_list else None
            else:
                if str(default_val).lower() != "none" and str(default_val).strip() != "":
                    computed[p_name] = (int(default_val),)
                else:
                    computed[p_name] = None
        else:
            computed[p_name] = default_val

    return computed


def sanitize_data(data, key_context=""):
    """Отладочная версия очистки данных."""
    if isinstance(data, dict):
        return {k: sanitize_data(v, key_context=f"{key_context}.{k}" if key_context else k) for k, v in data.items()}
    elif isinstance(data, list):
        cleaned = []
        for i, v in enumerate(data):
            res = sanitize_data(v, key_context=f"{key_context}[{i}]")
            if res is not None and str(res).lower() != "none":
                cleaned.append(res)
        return cleaned
    elif isinstance(data, str):
        val_stripped = data.strip()
        if val_stripped.lower() == "none" or val_stripped == "":
            return None
        if val_stripped.isdigit():
            try:
                return int(val_stripped)
            except ValueError as e:
                raise ValueError(f"Ошибка конвертации в число в поле '{key_context}': значение='{data}'") from e
    return data


def run_job(job_name: str, external_params: dict = None):
    """Главный оркестратор конвейера. Поднимает SSH-туннель, выполняет SQL и собирает Excel."""
    logger.info(f"===> Запуск конвейера для отчета: {job_name} <===")

    toml_config_path = os.path.join("config", "main.toml")
    db_config = {}
    ssh_config = {}

    if os.path.exists(toml_config_path):
        with open(toml_config_path, "rb") as f:
            global_config = tomllib.load(f)
            db_config = global_config.get("database", {})
            ssh_config = global_config.get("ssh", {})  # Читаем настройки SSH
    else:
        err = f"Критическая ошибка: Глобальный конфиг не найден по пути {toml_config_path}"
        logger.error(err)
        raise FileNotFoundError(err)

    if not db_config:
        raise ValueError(f"В файле {toml_config_path} отсутствует или пуста секция [database]")

    job_dir = os.path.join("jobs", job_name)
    config_path = os.path.join(job_dir, "config.yaml")

    if not os.path.exists(config_path):
        err = f"Файл конфигурации отчета не найден: {config_path}"
        logger.error(err)
        log_job_state(job_name, "Ошибка", err)
        raise FileNotFoundError(err)

    try:
        # 1. Чтение конфигурации отчета
        with open(config_path, "r", encoding="utf-8") as f:
            raw_job_config = yaml.safe_load(f)

        job_config = sanitize_data(raw_job_config)

        if not job_config.get("enabled", True):
            logger.info(f"Отчет '{job_name}' отключен в конфиге. Пропуск.")
            return

        # 2. Валидация и сборка параметров SQL
        param_declaration = job_config.get("parameters", {})
        final_params = {}

        if external_params:
            clean_external_params = sanitize_data(external_params)
            if not param_declaration:
                raise ValueError(f"Отчет '{job_name}' является статическим и не поддерживает работу с параметрами.")

            for p_name in param_declaration.keys():
                if p_name not in clean_external_params:
                    raise ValueError(f"Ошибка UI: Не передан обязательный параметр '{p_name}'")
                final_params[p_name] = clean_external_params[p_name]

            logger.info(f"Используются внешние параметры из интерфейса: {final_params}")
        else:
            if param_declaration:
                final_params = calculate_default_params(sanitize_data(param_declaration))
                logger.info(f"Автозапуск параметрического отчета. Сформированы дефолты: {final_params}")
            else:
                final_params = None
                logger.info("Статический отчет запущен без параметров.")

        if final_params:
            for k, v in list(final_params.items()):
                p_info = param_declaration.get(k, {})
                if p_info.get("type") == "int_list" and isinstance(v, (list, tuple)):
                    final_params[k] = tuple(int(x) for x in v if str(x).isdigit())

        # --- 3. ИНИЦИАЛИЗАЦИЯ ПОДКЛЮЧЕНИЯ (С SSH ИЛИ БЕЗ) ---
        sheets_data = {}
        wb_config = job_config.get("workbook", {})
        sheets_list = wb_config.get("sheets", [])

        if not sheets_list:
            raise ValueError("В конфигурации workbook.sheets не описана ни одна вкладка!")

        # Если в main.toml настроена секция [ssh], оборачиваем работу с БД в туннель
        if ssh_config and ssh_config.get("host"):
            logger.info(f"[SSH] Инициализация туннеля к {ssh_config['host']}...")

            # Определяем параметры аутентификации SSH
            ssh_port = int(ssh_config.get("port", 22))
            ssh_user = ssh_config.get("username")
            ssh_password = ssh_config.get("password")
            ssh_pkey = ssh_config.get("pkey")  # Путь к ключу (если используется вместо пароля)

            # Конечная цель туннеля на удаленном сервере (обычно локальный Postgres)
            remote_host = db_config.get("host", "127.0.0.1")
            remote_port = int(db_config.get("port", 5432))

            tunnel_kwargs = {
                "ssh_address_or_host": (ssh_config["host"], ssh_port),
                "ssh_username": ssh_user,
                "remote_bind_address": (remote_host, remote_port)
            }
            if ssh_pkey:
                tunnel_kwargs["ssh_pkey"] = ssh_pkey
            elif ssh_password:
                tunnel_kwargs["ssh_password"] = ssh_password

            # Запуск контекстного менеджера туннеля
            with SSHTunnelForwarder(**tunnel_kwargs) as tunnel:
                logger.info(f"[SSH] Туннель успешно открыт на локальном порту: {tunnel.local_bind_port}")

                # Подменяем конфиг БД для работы через локальный "конец" туннеля
                local_db_config = db_config.copy()
                local_db_config["host"] = "127.0.0.1"
                local_db_config["port"] = tunnel.local_bind_port

                # Создаем клиента БД внутри контекста работающего туннеля
                db = DBClient(local_db_config)

                # Выполняем SQL запросы для вкладок
                for sheet_cfg in sheets_list:
                    sheet_name = sheet_cfg.get("name", "Sheet1")
                    sql_filename = sheet_cfg.get("sql_file")
                    sql_file_path = os.path.join(job_dir, sql_filename)

                    df = db.execute_sql_file(sql_file_path, params=final_params)

                    allow_empty = job_config.get("validation", {}).get("allow_empty", True)
                    if df.empty and not allow_empty:
                        logger.warning(f"Вкладка '{sheet_name}' вернула 0 строк. Сборка прервана.")
                        log_job_state(job_name, "Пропущен (Пустой)")
                        return

                    column_mapping = sheet_cfg.get("columns", {})
                    if column_mapping:
                        df = df.rename(columns=column_mapping)

                    sheets_data[sheet_name] = df
            # Здесь блок 'with' завершается, туннель безопасно гасится автоматически.

        else:
            # ПРЯМОЕ ПОДКЛЮЧЕНИЕ (Если секция [ssh] отсутствует или пуста)
            logger.info("Подключение напрямую к базе данных (без SSH-туннеля).")
            db = DBClient(db_config)

            for sheet_cfg in sheets_list:
                sheet_name = sheet_cfg.get("name", "Sheet1")
                sql_filename = sheet_cfg.get("sql_file")
                sql_file_path = os.path.join(job_dir, sql_filename)

                df = db.execute_sql_file(sql_file_path, params=final_params)

                allow_empty = job_config.get("validation", {}).get("allow_empty", True)
                if df.empty and not allow_empty:
                    logger.warning(f"Вкладка '{sheet_name}' вернула 0 строк. Сборка прервана.")
                    log_job_state(job_name, "Пропущен (Пустой)")
                    return

                column_mapping = sheet_cfg.get("columns", {})
                if column_mapping:
                    df = df.rename(columns=column_mapping)

                sheets_data[sheet_name] = df

        # 5. Сборка Excel файла (вынесено за пределы блока туннеля, данные уже в памяти)
        excel_file_path = build_excel_workbook(sheets_data, job_config)

        # УНИВЕРСАЛЬНЫЙ ПОИСК НАЗВАНИЯ ОТЧЕТА
        try:
            # Сначала ищем title или name внутри секции report
            # Если не нашли — ищем title или name на самом верхнем уровне конфига
            # Если и там пусто — берем техническое имя папки (job_name)
            job_title = (
                    job_config.get("report", {}).get("title") or
                    job_config.get("report", {}).get("name") or
                    job_config.get("title") or
                    job_config.get("name") or
                    job_name
            )
        except Exception:
            job_title = job_name

        log_job_state(job_name, "Успешно", job_title=job_title)
        logger.info(f"===> Отчет '{job_name}' успешно сгенерирован: {excel_file_path} <===")
        return excel_file_path

    except Exception as err:
        error_msg = str(err)
        logger.error(f"Критический сбой конвейера '{job_name}': {error_msg}")
        # Защита на случай, если упало ДО того, как прочитался конфиг
        try:
            j_title = (
                    job_config.get("report", {}).get("title") or
                    job_config.get("report", {}).get("name") or
                    job_config.get("title") or
                    job_config.get("name") or
                    job_name
            )
        except NameError:
            j_title = job_name
        log_job_state(job_name, "Ошибка", j_title, error_msg)
        raise err
