import os
import time
import sqlite3
import requests
import paramiko

# Защита от потенциальной несовместимости новых версий paramiko и старых sshtunnel в потоках бота
if not hasattr(paramiko, 'DSSKey'):
    class DummyDSSKey:
        pass


    paramiko.DSSKey = DummyDSSKey

# Импортируем движок генератора отчетов и утилиты из вашего текущего main.py
from main import get_all_jobs, run_job

# --- НАСТРОЙКИ БОТА И ЯНДЕКС.МЕССЕНДЖЕРА ---
BOT_TOKEN = "y0__wgBEJCjte8IGJaREyCp4pnhF5XNg8JEA5PT2CbrToklWlr_bBnN"  # Поместите сюда ваш реальный токен
BOT_USERNAME = "LLO_reports"  # Имя вашего бота в системе Яндекса
API_URL = "https://botapi.messenger.yandex.net/v1/messages"
HEADERS = {"Authorization": f"OAuth {BOT_TOKEN}"}
DB_PATH = os.path.join(os.getcwd(), "data", "job_status.db")


def check_access_and_register_guest(yandex_id: str, first_name: str = "", last_name: str = "") -> bool:
    """
    Проверяет доступ пользователя в БД.
    Если пользователя нет в базе — автоматически создает запись 'гостя' (is_active = 0).
    Возвращает True, если доступ разрешен, иначе False.
    """
    if not yandex_id:
        return False

    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Сборка красивого ФИО на основе данных от Яндекса
    full_name = f"{last_name} {first_name}".strip() or "Анонимный сотрудник"

    try:
        # Ищем пользователя по yandex_id
        cursor.execute("SELECT is_active FROM users WHERE yandex_id = ?", (str(yandex_id),))
        row = cursor.fetchone()

        if row is not None:
            # Пользователь уже существует, возвращаем его статус активности (1 или 0)
            return bool(row[0])

        # Пользователь абсолютно новый — регистрируем его как заблокированного 'гостя'
        cursor.execute("""
                       INSERT INTO users (username, display_name, yandex_id, is_active)
                       VALUES (?, ?, ?, 0)
                       """, (f"yandex_{yandex_id}", full_name, str(yandex_id)))

        conn.commit()
        print(f"[SECURITY] Автоматически создана заявка на доступ: {full_name} (ID: {yandex_id})")
        return False

    except Exception as e:
        print(f"[BOT SECURITY ERROR] Ошибка работы с таблицей users в SQLite: {e}")
        return False
    finally:
        conn.close()


def send_inline_buttons(chat_id: str, text: str, jobs_list: list):
    """Отправляет в чат (личный или групповой) сообщение со списком доступных отчетов в виде кнопок."""
    inline_keyboard = []

    for job in jobs_list:
        inline_keyboard.append([{
            "text": f"📊 {job}",
            "callback_data": f"run:{job}"
        }])

    payload = {
        "chat_id": chat_id,
        "text": text,
        "inline_keyboard": inline_keyboard
    }
    try:
        requests.post(f"{API_URL}/sendText", json=payload, headers=HEADERS)
    except Exception as e:
        print(f"[BOT API ERROR] Ошибка отправки кнопок: {e}")


def send_document(chat_id: str, file_path: str, caption: str):
    """Физически отправляет сгенерированный Excel-файл пользователю в чат."""
    if not os.path.exists(file_path):
        print(f"[BOT ERROR] Попытка отправить несуществующий файл: {file_path}")
        return

    url = f"{API_URL}/sendFile"
    payload = {"chat_id": chat_id, "caption": caption}

    try:
        with open(file_path, "rb") as f:
            files = {"file": f}
            requests.post(url, data=payload, files=files, headers=HEADERS)
    except Exception as e:
        print(f"[BOT API ERROR] Ошибка отправки файла: {e}")


def handle_updates():
    """Фоновый бесконечный цикл прослушивания обновлений от Яндекс.Мессенджера (Long Polling)."""
    offset = 0
    poll_timeout = 30  # Просим Яндекс держать соединение открытым до 30 секунд

    print(f"[BOT] Бот @{BOT_USERNAME} успешно запущен и слушает события...")

    while True:
        try:
            # Открываем длинный HTTP-запрос к API Яндекса
            url = f"https://botapi.messenger.yandex.net/v1/updates?offset={offset}&timeout={poll_timeout}"
            response = requests.get(url, headers=HEADERS, timeout=poll_timeout + 5).json()
            updates = response.get("updates", [])

            for update in updates:
                offset = update["update_id"] + 1

                user_id = None
                chat_id = None
                f_name = ""
                l_name = ""

                # Шаг А: Извлекаем метаданные в зависимости от типа события (обычное сообщение или клик по кнопке)
                if "message" in update:
                    user_data = update["message"]["from"]
                    user_id = user_data.get("id")
                    f_name = user_data.get("first_name", "")
                    l_name = user_data.get("last_name", "")
                    chat_id = update["message"]["chat"]["id"] - - Для
                    группы
                    тут
                    будет
                    ID
                    чата
                    LLO_reports

                elif "callback_query" in update:
                    user_data = update["callback_query"]["from"]
                    user_id = user_data.get("id")
                    f_name = user_data.get("first_name", "")
                    l_name = user_data.get("last_name", "")
                    chat_id = update["callback_query"]["message"]["chat"]["id"]

                # Шаг B: Рубеж контроля доступа (Белый список)
                if user_id:
                    is_allowed = check_access_and_register_guest(user_id, first_name=f_name, last_name=l_name)

                    if not is_allowed:
                        full_name = f"{l_name} {f_name}".strip() or f"ID: {user_id}"
                        deny_text = (
                            f"❌ Доступ ограничен\n\n"
                            f"Уважаемый(ая) {f_name}, у вашей учетной записи недостаточно прав для генерации отчетов через бота.\n"
                            f"Заявка для сотрудника **'{full_name}'** автоматически зарегистрирована в системе. "
                            f"Обратитесь к администратору для активации доступа."
                        )
                        requests.post(f"{API_URL}/sendText", json={"chat_id": chat_id, "text": deny_text},
                                      headers=HEADERS)
                        continue  # Сбрасываем итерацию, игнорируя команду

                # Шаг C: Обработка действий авторизованного сотрудника
                # 1. Если пришло текстовое сообщение/команда
                if "message" in update:
                    text = update["message"].get("text", "").strip()

                    # Список триггеров (включая имя бота для группового чата)
                    valid_commands = [
                        "/start", "отчеты", "Отчеты",
                        f"@{BOT_USERNAME}", f"@{BOT_USERNAME} отчеты", f"/start@{BOT_USERNAME}"
                    ]

                    if text in valid_commands:
                        jobs = get_all_jobs()
                        if jobs:
                            send_inline_buttons(chat_id, "Выберите необходимый отчет из списка ниже:", jobs)
                        else:
                            requests.post(f"{API_URL}/sendText", json={"chat_id": chat_id,
                                                                       "text": "📭 В системе пока нет настроенных отчетов в папке /jobs."},
                                          headers=HEADERS)
                    else:
                        # Если это личный чат, вежливо подсказываем. В группе — молчим, чтобы не спамить на обычный флуд.
                        if not chat_id.startswith("c/"):  # В Яндексе групповые чаты обычно имеют префикс c/
                            requests.post(f"{API_URL}/sendText", json={"chat_id": chat_id,
                                                                       "text": "🤖 Напишите 'отчеты' или введите /start, чтобы открыть меню."},
                                          headers=HEADERS)

                # 2. Если пользователь кликнул на встроенную кнопку отчета
                elif "callback_query" in update:
                    callback_data = update["callback_query"]["data"]

                    if callback_data.startswith("run:"):
                        job_name = callback_data.split(":")[1]

                        # Отправляем уведомление о начале работы конвейера прямо в чат выполнения
                        requests.post(f"{API_URL}/sendText", json={"chat_id": chat_id,
                                                                   "text": f"⏳ Запущен конвейер для отчета '{job_name}'...\nПодключаюсь к серверу и формирую Excel-файл. Пожалуйста, подождите."},
                                      headers=HEADERS)

                        try:
                            # Запуск единого пайплайна генерации отчета из main.py
                            excel_path = run_job(job_name)

                            # Отправка файла
                            send_document(chat_id, excel_path, caption=f"✅ Отчет '{job_name}' успешно сгенерирован!")
                        except Exception as e:
                            requests.post(f"{API_URL}/sendText", json={"chat_id": chat_id,
                                                                       "text": f"❌ Ошибка при генерации отчета '{job_name}':\n{e}"},
                                          headers=HEADERS)

            time.sleep(0.5)

        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as net_err:
            # Беззвучно переподключаемся при штатных таймаутах удержания соединения со стороны Яндекса
            print("[BOT NETWORK] Переподключение к серверам Яндекс.Мессенджера...")
            time.sleep(1)

        except Exception as ex:
            # Логируем только критические ошибки (БД, синтаксис, отсутствие файлов ядра)
            print(f"[BOT CRITICAL ERROR] Цикл обновлений прерван системной ошибкой: {ex}")
            time.sleep(5)


if __name__ == "__main__":
    handle_updates()