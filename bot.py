import os
import time
import sqlite3
import requests
import toml
import subprocess
import urllib3
from main import run_job, get_all_jobs
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Находим папку, где лежит сам файл main.py
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

# Если main.py лежит внутри папки 'src', то корень проекта — на уровень выше
if os.path.basename(CURRENT_DIR) == "src":
    BASE_DIR = os.path.dirname(CURRENT_DIR)
else:
    BASE_DIR = CURRENT_DIR

MAIN_CONFIG_PATH = os.path.join(BASE_DIR, "config", "main.toml")

try:
    config_data = toml.load(MAIN_CONFIG_PATH)
    yandex_config = config_data.get("delivery", {}).get("yandex_messenger", {})
    BOT_TOKEN = yandex_config.get("bot_token")
    BOT_USERNAME = yandex_config.get("bot_username", "LLO_reports")

    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN не найден в конфигурационном файле.")
except Exception as e:
    print(f"[💥 CRITICAL CONFIG ERROR]: {e}")
    exit(1)

# URLs и HEADERS на основе загруженного токена
UPDATES_URL = "https://botapi.messenger.yandex.net/bot/v1/messages/getUpdates"
SEND_TEXT_URL = "https://botapi.messenger.yandex.net/bot/v1/messages/sendText/"
SEND_FILE_URL = "https://botapi.messenger.yandex.net/bot/v1/messages/sendFile/"

HEADERS = {"Authorization": f"OAuth {BOT_TOKEN}", "Content-Type": "application/json"}
DB_PATH = os.path.join(os.getcwd(), "data", "job_status.db")


# (Далее идет стандартная функция check_access_and_register_guest к локальной job_status.db без изменений)

def check_access_and_register_guest(yandex_id: str, display_name: str = "") -> bool:
    if not yandex_id: return False
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    # Прямое подключение к локальной базе авторизации на диске Jump-сервера
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
    except Exception as conn_err:
        print(f"[DB CONNECTION FAILED]: Ошибка открытия локальной job_status.db: {conn_err}")
        return False

    full_name = display_name.strip() or "Анонимный сотрудник"
    try:
        # Проверяем, активирован ли пользователь администратором
        cursor.execute("SELECT is_active FROM users WHERE yandex_id = ?", (str(yandex_id),))
        row = cursor.fetchone()
        if row is not None:
            return bool(row[0])

        # Если пользователя нет в базе — создаем гостевую заявку со статусом 0 (активация руками)
        cursor.execute("INSERT INTO users (username, display_name, yandex_id, is_active) VALUES (?, ?, ?, 0)",
                       (f"yandex_{yandex_id}", full_name, str(yandex_id)))
        conn.commit()
        print(f"[SECURITY] Создана новая заявка на доступ: {full_name} (ID: {yandex_id})")
        return False
    except Exception as e:
        print(f"[SQLITE ERROR] Ошибка при работе с правами пользователей: {e}")
        return False
    finally:
        conn.close()

def process_bot_logic(update):
    """ Процессор логики: работа через текстовые команды-триггеры """
    chat_data = update.get('chat', {})
    chat_id = chat_data.get('id')

    user_data = update.get('from', {})
    user_id = user_data.get('id')
    display_name = user_data.get('display_name', '').strip()

    text = update.get('text', '').strip().lower()

    if not chat_id or not user_id:
        return

    # 1. Контроль доступа (Белый список)
    if not check_access_and_register_guest(user_id, display_name):
        deny_text = (
            f"❌ Доступ ограничен\n\n"
            f"Учетная запись '{display_name}' не активирована.\n"
            f"Заявка зарегистрирована автоматически. Обратитесь к администратору."
        )
        requests.post(SEND_TEXT_URL, json={"chat_id": chat_id, "text": deny_text}, headers=HEADERS, verify=False)
        return

    # 2. Перехват команды на запуск конкретного отчета (например: run:llo_pharmacy)
    if text.startswith("run:"):
        job_name = text.split("run:")[-1].strip()
        valid_jobs = get_all_jobs()

        if job_name in valid_jobs:
            requests.post(SEND_TEXT_URL, json={"chat_id": chat_id,
                                               "text": f"⏳ Запущен конвейер для отчета '{job_name}'...\nПодключаюсь к серверу БД. Пожалуйста, подождите."},
                          headers=HEADERS, verify=False)

            try:
                print(f"[DEBUG EXEC] Вызываем run_job('{job_name}')...")
                excel_path = run_job(job_name)

                # ==== ЛОГИ ДЛЯ ПРОВЕРКИ ПУТИ ====
                print(f"[DEBUG EXEC] Функция run_job вернула значение: '{excel_path}'")
                if excel_path:
                    print(f"[DEBUG EXEC] Проверка os.path.exists('{excel_path}'): {os.path.exists(excel_path)}")
                    if os.path.exists(excel_path):
                        print(f"[DEBUG EXEC] Размер файла на диске: {os.path.getsize(excel_path)} байт")
                # ===============================

                if excel_path and os.path.exists(excel_path):
                    file_name = os.path.basename(excel_path)
                    print(f"[DEBUG EXEC] Подготовка к отправке файла: {file_name}")

                    # Заголовки: для Multipart убираем Content-Type (requests сделает всё сам)
                    file_headers = {
                        "Authorization": f"OAuth {BOT_TOKEN}"
                    }

                    # Все текстовые параметры кладем строго в data (тело формы)
                    payload = {
                        "chat_id": str(chat_id),
                        "caption": f"✅ Отчет '{job_name}' успешно сформирован."
                    }

                    # Открываем файл и упаковываем в поле 'document'
                    with open(excel_path, "rb") as f:
                        files = {
                            "document": (file_name, f,
                                         "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                        }

                        print(f"[DEBUG EXEC] Отправка проверенного Multipart (поле 'document') на Яндекс...")
                        res = requests.post(
                            SEND_FILE_URL,
                            headers=file_headers,
                            data=payload,  # Параметры в теле
                            files=files,  # Файл в теле под ключом document
                            verify=False,
                            timeout=60
                        )

                    print(f"[DEBUG EXEC] Ответ Яндекса на отправку файла: Статус {res.status_code}, Текст: {res.text}")

                    if res.status_code == 200:
                        print(f"[DEBUG EXEC] Файл {file_name} успешно отправлен в чат!")
                    else:
                        requests.post(SEND_TEXT_URL, json={"chat_id": chat_id,
                                                           "text": f"❌ Ошибка шлюза Яндекса при передаче файла:\n{res.text}"},
                                      headers=HEADERS, verify=False)

            except Exception as e:
                print(f"[💥 ОШИБКА ГЕНЕРАЦИИ]: {e}")
                requests.post(SEND_TEXT_URL, json={"chat_id": chat_id, "text": f"❌ Ошибка генерации отчета:\n{e}"},
                              headers=HEADERS, verify=False)
        else:
            requests.post(SEND_TEXT_URL,
                          json={"chat_id": chat_id, "text": f"❓ Ошибка: Отчет '{job_name}' не найден в системе."},
                          headers=HEADERS, verify=False)
        return
    # 3. Вывод главного меню со списком доступных отчетов
    is_mentioned = False
    if 'mentioned_users' in update:
        for user in update['mentioned_users']:
            if user.get('login') == 'yndx-mssngr-ropgqhppgl-bot' or user.get('display_name') == 'LLO_reports':
                is_mentioned = True
                break

    if "/start" in text or "отчеты" in text or "llo_reports" in text or is_mentioned:
        jobs = get_all_jobs()
        if jobs:
            menu_text = "📋 **Доступные отчеты в системе LLO:**\n\n"
            menu_text += "Чтобы запустить сборку данных, скопируйте и отправьте в чат одну из команд:\n\n"
            for job in jobs:
                menu_text += f"🔹 run:{job}\n"

            requests.post(SEND_TEXT_URL, json={"chat_id": chat_id, "text": menu_text}, headers=HEADERS, verify=False)
        else:
            requests.post(SEND_TEXT_URL, json={"chat_id": chat_id, "text": "📭 В папке /jobs нет доступных отчетов."},
                          headers=HEADERS, verify=False)


def start_pooling():
    print(f"[BOT] Бот @{BOT_USERNAME} успешно запущен на Jump-сервере. Режим: Текстовые команды.")

    last_update_id = -1
    try:
        request_body = {'limit': 100, 'offset': 0}
        response = requests.post(UPDATES_URL, json=request_body, headers=HEADERS, verify=False)
        updates = response.json().get('updates', [])
        if len(updates) > 0:
            last_update_id = int(updates[-1]['update_id'])
    except Exception as e:
        print(f"[INIT] Ошибка синхронизации offset: {e}")

    while True:
        try:
            request_body = {'limit': 100, 'offset': last_update_id + 1}
            response = requests.post(UPDATES_URL, json=request_body, headers=HEADERS, verify=False, timeout=20)

            if response.status_code != 200:
                time.sleep(2)
                continue

            updates = response.json().get('updates', [])

            if len(updates) > 0:
                last_update_id = int(updates[-1]['update_id'])
                for update in updates:
                    try:
                        process_bot_logic(update)
                    except Exception as inner_ex:
                        print(f"[LOGIC ERROR] {inner_ex}")

        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            time.sleep(1)
        except Exception as ex:
            print(f"[CRITICAL ERROR] {ex}")
            time.sleep(4)

        time.sleep(1)


if __name__ == '__main__':
    start_pooling()