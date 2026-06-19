import os
import sys
import toml
import yaml  # Для чтения индивидуальных config.yaml отчетов
import sqlite3
import psycopg2
from datetime import datetime
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

# === КОСТЫЛЬ СОВМЕСТИМОСТИ ДЛЯ PARAMIKO & SSHTUNNEL ===
import paramiko

if not hasattr(paramiko, 'DSSKey'):
    class DummyDSSKey: pass
    paramiko.DSSKey = DummyDSSKey

from sshtunnel import SSHTunnelForwarder

# 1. Получаем абсолютный путь к папке, где физически лежит этот main.py
_current_dir = os.path.dirname(os.path.abspath(__file__))

# 2. Если main.py лежит в src, корень — на уровень выше. Иначе — это и есть корень.
if os.path.basename(_current_dir) == "src":
    BASE_DIR = os.path.dirname(_current_dir)
else:
    BASE_DIR = _current_dir

# 3. Абсолютные пути к ключевым точкам системы
MAIN_CONFIG_PATH = os.path.join(BASE_DIR, "config", "main.toml")
JOBS_DIR = os.path.join(BASE_DIR, "jobs")

print(f"[DEBUG PATHS] Корень проекта определен как: {BASE_DIR}")
print(f"[DEBUG PATHS] Центральный конфиг ищется по: {MAIN_CONFIG_PATH}")
print(f"[DEBUG PATHS] Папка с отчетами находится по: {JOBS_DIR}")


def get_connection_for_job(job_name):
    """
    Универсальная фабрика подключений.
    Динамически ищет конфигурацию БД в main.toml по ключу из секции [jobs].
    Никакого хардкода структуры секций или типов.
    """
    if not os.path.exists(MAIN_CONFIG_PATH):
        raise FileNotFoundError(f"Критическая ошибка: Главный конфиг не найден: {MAIN_CONFIG_PATH}")

    config = toml.load(MAIN_CONFIG_PATH)
    jobs_section = config.get("jobs", {})
    db_profile_key = jobs_section.get(job_name)

    if not db_profile_key:
        raise ValueError(f"Отчет '{job_name}' не зарегистрирован в секции [jobs] в main.toml")

    # --- ДИНАМИЧЕСКИЙ ПОИСК ПРОФИЛЯ ПО КЛЮЧУ ---
    # Поддерживает как "database.postgres_prod", так и вложенные структуры любой глубины
    db_config = config
    for part in db_profile_key.split('.'):
        if isinstance(db_config, dict):
            db_config = db_config.get(part)
        else:
            db_config = None
            break

    if not db_config or not isinstance(db_config, dict):
        raise ValueError(f"Конфигурация подключения [{db_profile_key}] не найдена или некорректна в main.toml")
    # --------------------------------------------

    # Определяем тип СУБД строго из параметров самого профиля в TOML
    db_type = db_config.get("type")

    # 1. Режим СУБД: SQLite
    if db_type == "sqlite":
        db_path = db_config.get("database")
        print(f"[ENGINE] Подключение к локальной СУБД SQLite: {db_path}")
        return sqlite3.connect(db_path), None

    # 2. Режим СУБД: PostgreSQL
    if db_type == "postgres":
        if db_config.get("use_ssh", False):
            print(f"[ENGINE] Инициализация SSH-туннеля для профиля [{db_profile_key}]...")
            try:
                tunnel_kwargs = {
                    "ssh_address_or_host": (db_config.get("ssh_host"), int(db_config.get("ssh_port", 22))),
                    "ssh_username": db_config.get("ssh_user"),
                    "remote_bind_address": (db_config.get("host"), int(db_config.get("port", 5432)))
                }

                # Загрузка учетных данных SSH из TOML
                if db_config.get("ssh_password"):
                    tunnel_kwargs["ssh_password"] = db_config.get("ssh_password")
                elif db_config.get("ssh_pkey"):
                    clean_key_path = os.path.normpath(db_config.get("ssh_pkey"))
                    if os.path.exists(clean_key_path):
                        try:
                            tunnel_kwargs["ssh_pkey"] = paramiko.RSAKey.from_private_key_file(clean_key_path)
                        except Exception:
                            tunnel_kwargs["ssh_pkey"] = paramiko.Ed25519Key.from_private_key_file(clean_key_path)
                    else:
                        raise FileNotFoundError(f"Файл SSH-ключа не найден: {clean_key_path}")

                tunnel = SSHTunnelForwarder(**tunnel_kwargs)
                tunnel.start()
                print(f"[ENGINE] SSH-туннель успешно поднят на локальном порту: {tunnel.local_bind_port}")

                # Подключение к Postgres через локальную точку туннеля
                conn = psycopg2.connect(
                    host='127.0.0.1',
                    port=tunnel.local_bind_port,
                    user=db_config.get("user"),
                    password=db_config.get("password"),
                    database=db_config.get("database"),
                    connect_timeout=10
                )
                return conn, tunnel
            except Exception as e:
                print(f"[💥 ENGINE ERROR] Сбой SSH-туннелирования: {e}")
                raise e
        else:
            # Прямое подключение к Postgres (без SSH) на основе параметров TOML
            target_host = db_config.get("host")
            target_port = int(db_config.get("port", 5432))
            print(f"[ENGINE] Прямое подключение к СУБД Postgres ({target_host}:{target_port})...")
            conn = psycopg2.connect(
                host=target_host,
                port=target_port,
                user=db_config.get("user"),
                password=db_config.get("password"),
                database=db_config.get("database"),
                connect_timeout=10
            )
            return conn, None

    raise ValueError(f"Неподдерживаемый тип СУБД '{db_type}' в профиле конфигурации [{db_profile_key}]")


def get_all_jobs():
    """ Динамический список задач из центрального TOML """
    try:
        config = toml.load(MAIN_CONFIG_PATH)
        return list(config.get("jobs", {}).keys())
    except Exception:
        return []


def handle_delivery(job_config, file_path):
    """
    Блок дистрибуции отчета на основе секции delivery в индивидуальном config.yaml
    """
    delivery = job_config.get("delivery", {})
    if not delivery:
        return

    # Локальное сохранение/архивирование
    local_cfg = delivery.get("local", {})
    if local_cfg.get("enabled"):
        target_dir = local_cfg.get("target_path")
        if target_dir:
            try:
                os.makedirs(target_dir, exist_ok=True)
                import shutil
                shutil.copy(file_path, os.path.join(target_dir, os.path.basename(file_path)))
                print(f"[DELIVERY] Файл успешно скопирован в локальный архив: {target_dir}")
            except Exception as e:
                print(f"[💥 DELIVERY ERROR] Локальное архивирование сорвалось: {e}")

    # Интеграция с внешними сервисами доставки при необходимости настраивается здесь
    if delivery.get("mail", {}).get("enabled"):
        print("[DELIVERY] Внешняя рассылка Mail активна (параметры из main.toml)...")

    if delivery.get("nextcloud", {}).get("enabled"):
        print("[DELIVERY] Внешняя выгрузка в Nextcloud активна...")


def run_job(job_name, user_params=None):
    """
    Основной конвейер. Читает config.yaml из папки отчета,
    выполняет SQL-запросы для каждой вкладки, производит маппинг колонок,
    валидирует результат и запускает дистрибуцию.
    """
    if user_params is None:
        user_params = {}

    print(f"\n[WORKER] Инициализация конвейера отчета: {job_name}")

    # Строим пути строго на основе глобальной JOBS_DIR
    job_dir = os.path.join(JOBS_DIR, job_name)
    yaml_path = os.path.join(job_dir, "config.yaml")

    if not os.path.exists(yaml_path):
        raise FileNotFoundError(f"Критическая ошибка: Конфигурационный файл {yaml_path} не найден!")

    if not os.path.exists(yaml_path):
         raise FileNotFoundError(f"Критическая ошибка: Конфигурационный файл {yaml_path} не найден!")

    with open(yaml_path, "r", encoding="utf-8") as f:
        job_config = yaml.safe_load(f)

    if not job_config.get("enabled", True):
        print(f"[WORKER] Генерация отчета '{job_name}' отменена: статус 'enabled: false'")
        return None

    workbook_cfg = job_config.get("workbook", {})
    sheets_cfg = workbook_cfg.get("sheets", [])

    if not sheets_cfg:
        raise ValueError(f"Конфигурация '{job_name}' не содержит описания листов книги (sheets)")

    # Подключаемся к базе, используя полностью динамический парсер профилей
    conn, tunnel = get_connection_for_job(job_name)
    cursor = conn.cursor()

    try:
        wb = openpyxl.Workbook()
        # Сразу удаляем дефолтный лист, чтобы генерировать только вкладки из config.yaml
        wb.remove(wb.active)

        # Стилизация книги
        header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="365F91", end_color="365F91", fill_type="solid")
        center_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        thin_border = Border(left=Side(style="thin", color="D9D9D9"), right=Side(style="thin", color="D9D9D9"),
                             top=Side(style="thin", color="D9D9D9"), bottom=Side(style="thin", color="D9D9D9"))

        # Обработка каждой вкладки отчета последовательно
        for sheet_idx, sheet_info in enumerate(sheets_cfg):
            sheet_name = sheet_info.get("name", f"Лист {sheet_idx + 1}")
            sql_file_name = sheet_info.get("sql_file")
            columns_mapping = sheet_info.get("columns", {}) or {}

            sql_file_path = os.path.join(job_dir, sql_file_name)
            if not os.path.exists(sql_file_path):
                raise FileNotFoundError(f"Не найден файл запроса {sql_file_path} для листа '{sheet_name}'")

            with open(sql_file_path, "r", encoding="utf-8") as sf:
                sql_query = sf.read()

            print(f"[ENGINE] Сбор данных для листа '{sheet_name}' (SQL: {sql_file_name})...")

            # Выполнение SQL с безопасной подстановкой переданных параметров отчета
            cursor.execute(sql_query, user_params)
            rows = cursor.fetchall()

            # Валидация на пустые выборки на основе правил из config.yaml
            validation = job_config.get("validation", {})
            if len(rows) == 0 and not validation.get("allow_empty", True):
                if validation.get("on_empty_action") == "alert":
                    raise ValueError(
                        f"Критический сбой валидации данных: Вкладка '{sheet_name}' пуста. Выполнение прервано.")

            # Создание целевой вкладки
            ws = wb.create_sheet(title=sheet_name)
            ws.views.sheetView[0].showGridLines = True

            # Читаем оригинальные системные имена столбцов, возвращенные СУБД
            db_columns = [desc[0] for desc in cursor.description]
            # Маппим оригинальные имена колонок в пользовательские русские имена из config.yaml
            headers = [columns_mapping.get(col, col) for col in db_columns]

            # Добавление и стилизация шапки таблицы
            ws.append(headers)
            for col_num in range(1, len(headers) + 1):
                cell = ws.cell(row=1, column=col_num)
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = center_alignment
                cell.border = thin_border

            # Заполнение данными
            for row_data in rows:
                clean_row = [item.strftime("%Y-%m-%d %H:%M:%S") if isinstance(item, datetime) else item for item in
                             row_data]
                ws.append(clean_row)
                current_row = ws.max_row
                for col_num in range(1, len(clean_row) + 1):
                    ws.cell(row=current_row, column=col_num).border = thin_border

            # Корректировка ширины столбцов под размер контента
            for col in ws.columns:
                max_len = max(len(str(cell.value or '')) for cell in col)
                col_letter = openpyxl.utils.get_column_letter(col[0].column)
                ws.column_dimensions[col_letter].width = max(max_len + 3, 12)

            ws.freeze_panes = "A2"

        # Сборка финального имени файла по маске filename_template
        template = workbook_cfg.get("filename_template", f"{job_name}_{{YYYY}}_{{MM}}_{{DD}}.xlsx")
        now = datetime.now()
        filename = template.format(
            YYYY=now.strftime("%Y"),
            MM=now.strftime("%m"),
            DD=now.strftime("%d")
        )

        output_file_path = os.path.join(os.getcwd(), "output", filename)
        os.makedirs(os.path.dirname(output_file_path), exist_ok=True)

        wb.save(output_file_path)
        wb.close()
        print(f"[EXCEL] Книга Excel успешно сформирована: {output_file_path}")

        # Локальная или облачная дистрибуция готового файла
        handle_delivery(job_config, output_file_path)

        return os.path.abspath(output_file_path)

    except Exception as err:
        print(f"[💥 WORKER ERROR] Ошибка генерации отчета '{job_name}': {err}")
        raise err
    finally:
        cursor.close()
        conn.close()
        if tunnel:
            tunnel.stop()
            print("[ENGINE] Сессия SSH-туннеля закрыта.")


if __name__ == "__main__":
    print("=== Запуск движка отчетов с динамической фабрикой СУБД ===")
    try:
        # Тест с передачей параметров (если они требуются вашим .sql скриптам)
        path = run_job("llo_pharmacy", user_params={"status_id": 1})
        print(f"[УСПЕХ] Готовый файл находится здесь:\n{path}")
    except Exception as e:
        print(f"[ОШИБКА]: {e}")