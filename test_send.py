import os
import requests
import urllib3

# Отключаем варнинги в консоли
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- КОНФИГУРАЦИЯ ТЕСТА ---
BOT_TOKEN = "y0__wgBEJCjte8IGJaREyCp4pnhF5XNg8JEA5PT2CbrToklWlr_bBnN"
CHAT_ID = "0/0/9e897d81-a8c2-444c-b1a8-5f6659f2580d"  # ID вашей группы LLO_reports
URL = "https://botapi.messenger.yandex.net/bot/v1/messages/sendFile/"

# Путь к файлу, который точно существует (возьмем тот самый из логов)
FILE_PATH = r"C:\Users\Boris\work\py\universal_reporter\output\Аптеки_2026_06_18.xlsx"


def test_send_variant_1():
    print("\n--- [ТЕСТ #1] Классический Multipart (Параметры в URL, файл в теле) ---")

    headers = {
        "Authorization": f"OAuth {BOT_TOKEN}"
    }

    params = {
        "chat_id": CHAT_ID,
        "caption": "Тест #1: Отправка через params+files"
    }

    if not os.path.exists(FILE_PATH):
        print(f"❌ Ошибка: Тестовый файл не найден по пути {FILE_PATH}")
        return

    with open(FILE_PATH, "rb") as f:
        # Яндекс часто требует имя поля 'file'
        files = {
            "file": (os.path.basename(FILE_PATH), f,
                     "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        }

        try:
            res = requests.post(URL, headers=headers, params=params, files=files, verify=False, timeout=30)
            print(f"Статус ответа: {res.status_code}")
            print(f"Текст ответа: {res.text}")
        except Exception as e:
            print(f"💥 Сбой сети: {e}")


def test_send_variant_2():
    print("\n--- [ТЕСТ #2] Чистый Multipart формы (Все параметры внутри тела) ---")

    headers = {
        "Authorization": f"OAuth {BOT_TOKEN}"
    }

    # Переносим chat_id внутрь тела запроса (data)
    data = {
        "chat_id": CHAT_ID,
        "caption": "Тест #2: Все данные в теле формы"
    }

    with open(FILE_PATH, "rb") as f:
        # Пробуем альтернативное имя поля 'document', которое используется в некоторых ветках API Яндекс 360
        files = {
            "document": (os.path.basename(FILE_PATH), f,
                         "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        }

        try:
            res = requests.post(URL, headers=headers, data=data, files=files, verify=False, timeout=30)
            print(f"Статус ответа: {res.status_code}")
            print(f"Текст ответа: {res.text}")
        except Exception as e:
            print(f"💥 Сбой сети: {e}")


if __name__ == "__main__":
    print(f"Запуск изолированного тестирования отправки файла...")
    test_send_variant_1()
    test_send_variant_2()