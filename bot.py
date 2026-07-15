import os
import time
import sqlite3
import requests
import toml
import urllib3
import yaml
from main import run_job, get_all_jobs, JOBS_DIR
from src.utils.db_logger import log_user_run
from src.utils.config_loader import load_job_config, get_job_title

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
ANSWER_CALLBACK_URL = "https://botapi.messenger.yandex.net/bot/v1/messages/answerCallbackQuery/"

HEADERS = {"Authorization": f"OAuth {BOT_TOKEN}", "Content-Type": "application/json"}
DB_PATH = os.path.join(os.getcwd(), "data", "job_status.db")

# Хранение состояния пользователей для ввода параметров
# Формат: {user_id: {"job_name": str, "param_index": int, "params": dict, "defined_params": dict, "menu_level": str, "current_category": str}}
user_states = {}


def create_categories_keyboard(jobs):
    """Создает клавиатуру с категориями"""
    # Собираем уникальные категории
    categories = set()
    
    for job in jobs:
        job_config = load_job_config(job, JOBS_DIR)
        if job_config and "category" in job_config:
            categories.add(job_config["category"])
    
    if not categories:
        categories.add("Без категории")
    
    # Формируем клавиатуру с кнопками категорий
    inline_keyboard = []
    
    for category in sorted(categories):
        inline_keyboard.append({
            "text": f"📁 {category}",
            "callback_data": {
                "data": f"category:{category}",
                "request_id": int(time.time() * 1000)
            }
        })
    
    return inline_keyboard


def create_jobs_keyboard(jobs, category):
    """Создает клавиатуру с задачами для конкретной категории"""
    inline_keyboard = []
    
    for job in jobs:
        job_config = load_job_config(job, JOBS_DIR)
        
        job_title = job
        job_category = "Без категории"
        
        if job_config:
            if "title" in job_config:
                job_title = job_config["title"]
            if "category" in job_config:
                job_category = job_config["category"]
        
        # Добавляем только задачи из указанной категории
        if job_category == category:
            inline_keyboard.append({
                "text": f"📊 {job_title}",
                "callback_data": {
                    "data": f"run:{job}",
                    "request_id": int(time.time() * 1000)
                }
            })
    
    # Добавляем кнопку "Назад"
    inline_keyboard.append({
        "text": "⬅️ Назад к категориям",
        "callback_data": {
            "data": "back_to_categories",
            "request_id": int(time.time() * 1000)
        }
    })
    
    return inline_keyboard


def create_inline_keyboard(jobs):
    """Создает inline клавиатуру в формате Яндекс Messenger с группировкой по категориям"""
    # Группируем задачи по категориям
    categories = {}
    
    for job in jobs:
        job_config = load_job_config(job, JOBS_DIR)
        
        job_title = job
        job_category = "Без категории"  # Категория по умолчанию
        
        if job_config:
            if "title" in job_config:
                job_title = job_config["title"]
            if "category" in job_config:
                job_category = job_config["category"]
        
        if job_category not in categories:
            categories[job_category] = []
        
        categories[job_category].append({
            "text": f"📊 {job_title}",
            "callback_data": {
                "data": f"run:{job}",
                "request_id": int(time.time() * 1000)
            }
        })
    
    # Формируем плоскую клавиатуру с префиксами категорий в названиях кнопок
    inline_keyboard = []
    
    # Сортируем категории по алфавиту
    for category in sorted(categories.keys()):
        # Добавляем кнопки задач этой категории с префиксом категории
        for job_button in categories[category]:
            job_button["text"] = f"[{category}] {job_button['text']}"
            inline_keyboard.append(job_button)
    
    return inline_keyboard


def check_access_and_register_guest(yandex_id: str, display_name: str = "") -> bool:
    if not yandex_id: return False
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
    except Exception as conn_err:
        print(f"[DB CONNECTION FAILED]: Ошибка открытия локальной job_status.db: {conn_err}")
        return False

    full_name = display_name.strip() or "Анонимный сотрудник"
    try:
        cursor.execute("SELECT is_active FROM users WHERE yandex_id = ?", (str(yandex_id),))
        row = cursor.fetchone()
        if row is not None:
            return bool(row[0])

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
    """ Процессор логики: работа через текстовые команды-триггеры с поддержкой параметров """
    chat_data = update.get('chat', {})
    chat_id = chat_data.get('id')

    user_data = update.get('from', {})
    user_id = user_data.get('id')
    display_name = user_data.get('display_name', '').strip()

    # Проверяем, является ли это callback query от кнопки
    callback_query = update.get('callback_query')
    if callback_query:
        callback_id = callback_query.get('id')
        callback_data = callback_query.get('data', '')
        callback_user = callback_query.get('from', {})
        callback_user_id = callback_user.get('id')
        callback_display_name = callback_user.get('display_name', '').strip()
        
        # Отвечаем на callback, чтобы убрать индикатор загрузки
        try:
            requests.post(ANSWER_CALLBACK_URL, json={"callback_query_id": callback_id}, headers=HEADERS, verify=False)
        except Exception as e:
            print(f"[CALLBACK ERROR] Не удалось ответить на callback: {e}")
        
        # Проверяем доступ
        if not check_access_and_register_guest(callback_user_id, callback_display_name):
            deny_text = (
                f"❌ Доступ ограничен\n\n"
                f"Учетная запись '{callback_display_name}' не активирована.\n"
                f"Заявка зарегистрирована автоматически. Обратитесь к администратору."
            )
            requests.post(SEND_TEXT_URL, json={"chat_id": chat_id, "text": deny_text}, headers=HEADERS, verify=False)
            return
        
        # Обрабатываем callback - callback_data теперь объект
        if isinstance(callback_data, dict):
            data_value = callback_data.get('data', '')
        else:
            data_value = callback_data
        
        if data_value.startswith('run:'):
            job_name = data_value.split(':', 1)[-1].strip()
            execute_job(chat_id, job_name, {}, callback_user_id, callback_display_name)
        elif data_value.startswith('category:'):
            # Показываем задачи выбранной категории
            category = data_value.split(':', 1)[-1].strip()
            jobs = get_all_jobs()
            inline_keyboard = create_jobs_keyboard(jobs, category)
            
            menu_text = f"📋 **Категория: {category}**\n\nВыберите отчет для запуска:"
            
            payload = {
                "chat_id": chat_id,
                "text": menu_text,
                "inline_keyboard": inline_keyboard
            }
            
            requests.post(SEND_TEXT_URL, json=payload, headers=HEADERS, verify=False)
        elif data_value == 'back_to_categories':
            # Возвращаемся к списку категорий
            jobs = get_all_jobs()
            inline_keyboard = create_categories_keyboard(jobs)
            
            menu_text = "📋 **Доступные категории отчетов:**\n\nВыберите категорию для просмотра отчетов:"
            
            payload = {
                "chat_id": chat_id,
                "text": menu_text,
                "inline_keyboard": inline_keyboard
            }
            
            requests.post(SEND_TEXT_URL, json=payload, headers=HEADERS, verify=False)
        return
    
    # Получаем текст и ОЧИЩАЕМ его от обратных кавычек, которые добавляет Яндекс для кода
    raw_text = update.get('text', '').strip()
    if raw_text:
        raw_text = raw_text.replace("`", "").strip()  # <-- ВОТ ЭТА СТРОКА ОЧИСТИТ ВВОД
    # === САМЫЙ ГЛАВНЫЙ ТОЧЕЧНЫЙ ДЕБАГ ВЫШЕ ВСЕХ ПРОВЕРОК ===
    if raw_text:
        print(f"\n[СЕРВЕР ЯНДЕКСА ПРИСЛАЛ ТЕКСТ]: '{raw_text}'")
        print(f"[АНАЛИЗ] Начинается ли с 'run:': {raw_text.lower().startswith('run:')}")
    # ======================================================
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

    # 2. Перехват команды на запуск конкретного отчета (с поддержкой параметров)
    if raw_text.lower().startswith("run:"):
        # === КРИТИЧЕСКИЙ ДЕБАГ-ЛОГ ===
        print(f"\n[ВХОДЯЩАЯ КОМАНДА] Получен текст: '{raw_text}'")

        tokens = raw_text.split()
        print(f"[DEB] Токены строки: {tokens}")

        if not tokens:
            return

        command_part = tokens[0]  # 'run:job_name'
        job_name = command_part.split(":", 1)[-1].strip()

        valid_jobs = get_all_jobs()
        print(f"[DEB] Выделенное имя задачи: '{job_name}'")
        print(f"[DEB] Список зарегистрированных в main.toml задач: {valid_jobs}")
        print(f"[DEB] Входит ли задача в список разрешенных: {job_name in valid_jobs}")
        # =============================

        if job_name in valid_jobs:
            provided_args = tokens[1:]

            # Читаем config.yaml отчета
            job_config = load_job_config(job_name, JOBS_DIR)
            defined_params = job_config.get("parameters", {}) or {}
            require_params = job_config.get("require_parameters", False)

            param_keys = list(defined_params.keys())

            # СЦЕНАРИЙ А: Аргументы в чате не переданы, но параметры у отчета есть
            if len(provided_args) == 0 and len(param_keys) > 0:

                # 1. Собираем красивую строку примера на основе дефолтных значений из config.yaml
                example_values = []
                for k in param_keys:
                    p_info = defined_params.get(k, {})
                    if isinstance(p_info, dict) and "default" in p_info:
                        example_values.append(str(p_info["default"]))
                    else:
                        example_values.append("значение")

                example_string = " ".join(example_values)

                # 2. подстраиваем текст под тип параметров
                if len(param_keys) == 1:
                    instruction_text = "передав значение параметра (для отправки списка используйте запятую **,**):"
                else:
                    instruction_text = "передав аргументы через пробел (если внутри параметра нужен список — указывайте его через запятую без пробелов):"

                # Вариант 1: Жесткий запрет запуска без параметров (require_parameters: true)
                if require_params:
                    alert_text = (
                            f"⚠️ **Ошибка запуска отчета '{job_name}'**\n\n"
                            f"Этот отчет содержит конфиденциальные или объемные данные, "
                            f"его **запрещено** запускать без параметров!\n\n"
                            f"Пожалуйста, повторите команду, {instruction_text}\n"
                            f"`run:{job_name} " + " ".join([f"[{k}]" for k in param_keys]) + "`\n\n"
                                                                                             f"💡 *Пример запуска:* `run:{job_name} {example_string}`"
                    )
                    requests.post(SEND_TEXT_URL, json={"chat_id": chat_id, "text": alert_text}, headers=HEADERS,
                                  verify=False)
                    return

                # Вариант 2: Пустой запуск разрешен, выводим стандартную подсказку по типам
                else:
                    help_text = f"📋 **Справка по параметрам для отчета '{job_name}':**\n\n"
                    help_text += f"Чтобы запустить отчет с кастомными значениями, повторите команду, {instruction_text}\n"
                    help_text += f"`run:{job_name} " + " ".join([f"[{k}]" for k in param_keys]) + "`\n\n"
                    help_text += "**Ожидаемые параметры:**\n"

                    for idx, (p_name, p_info) in enumerate(defined_params.items(), 1):
                        p_type = p_info.get("type", "строка") if isinstance(p_info, dict) else "не указан"
                        p_def = p_info.get("default", "нет") if isinstance(p_info, dict) else "нет"
                        p_label = p_info.get("label", "") if isinstance(p_info, dict) else ""

                        label_str = f" ({p_label})" if p_label else ""
                        help_text += f"{idx}. **{p_name}**{label_str} — Тип: `{p_type}`, По умолчанию: `{p_def}`\n"

                    help_text += f"\n💡 *Пример запуска:* `run:{job_name} {example_string}`"

                    requests.post(SEND_TEXT_URL, json={"chat_id": chat_id, "text": help_text}, headers=HEADERS,
                                  verify=False)
                    return

            # СЦЕНАРИЙ Б: Параметры переданы (или у отчета вообще нет параметров), формируем словарь
            user_params = {}
            for i, k in enumerate(param_keys):
                if i < len(provided_args):
                    user_params[k] = provided_args[i].strip()
                else:
                    if isinstance(defined_params[k], dict):
                        user_params[k] = defined_params[k].get("default")

            execute_job(chat_id, job_name, user_params, user_id, display_name)
        else:
            requests.post(SEND_TEXT_URL,
                          json={"chat_id": chat_id, "text": f"❓ Ошибка: Отчет '{job_name}' не найден в системе."},
                          headers=HEADERS, verify=False)
        return

    # 3. Обработка нажатия на кнопку категории (текст начинается с 📁)
    if raw_text.startswith("📁"):
        category = raw_text.replace("📁", "").strip()
        jobs = get_all_jobs()
        inline_keyboard = create_jobs_keyboard(jobs, category)
        
        menu_text = f"📋 **Категория: {category}**\n\nВыберите отчет для запуска:"
        
        payload = {
            "chat_id": chat_id,
            "text": menu_text,
            "inline_keyboard": inline_keyboard
        }
        
        requests.post(SEND_TEXT_URL, json=payload, headers=HEADERS, verify=False)
        return

    # 4. Обработка кнопки "Назад к категориям"
    if raw_text == "⬅️ Назад к категориям":
        jobs = get_all_jobs()
        inline_keyboard = create_categories_keyboard(jobs)
        
        menu_text = "📋 **Доступные категории отчетов:**\n\nВыберите категорию для просмотра отчетов:"
        
        payload = {
            "chat_id": chat_id,
            "text": menu_text,
            "inline_keyboard": inline_keyboard
        }
        
        requests.post(SEND_TEXT_URL, json=payload, headers=HEADERS, verify=False)
        return

    # 5. Вывод главного меню со списком доступных отчетов
    text_lower = raw_text.lower()
    is_mentioned = False
    if 'mentioned_users' in update:
        for user in update['mentioned_users']:
            if user.get('login') == 'yndx-mssngr-ropgqhppgl-bot' or user.get('display_name') == 'LLO_reports':
                is_mentioned = True
                break

    if "/start" in text_lower or "отчеты" in text_lower or "llo_reports" in text_lower or is_mentioned or not raw_text:
        jobs = get_all_jobs()
        if jobs:
            menu_text = "📋 **Доступные категории отчетов:**\n\n"
            menu_text += "Выберите категорию для просмотра отчетов:\n\n"
            
            inline_keyboard = create_categories_keyboard(jobs)
            
            payload = {
                "chat_id": chat_id,
                "text": menu_text,
                "inline_keyboard": inline_keyboard
            }
            
            response = requests.post(SEND_TEXT_URL, json=payload, headers=HEADERS, verify=False)
            print(f"[BUTTONS DEBUG] Response status: {response.status_code}")
            print(f"[BUTTONS DEBUG] Response text: {response.text}")
        else:
            requests.post(SEND_TEXT_URL,
                          json={"chat_id": chat_id, "text": "📭 В папке /jobs нет доступных отчетов."},
                          headers=HEADERS, verify=False)
        return
    
    # 4. Обработка ввода параметров (если пользователь в состоянии ожидания)
    if user_id in user_states:
        # Проверка на команду отмены
        if raw_text.lower() in ['/cancel', '/отмена', 'отмена', 'cancel']:
            del user_states[user_id]
            requests.post(SEND_TEXT_URL, json={"chat_id": chat_id, "text": "❌ Ввод параметров отменен."}, headers=HEADERS, verify=False)
            return
        
        state = user_states[user_id]
        param_index = state["param_index"]
        defined_params = state["defined_params"]
        param_keys = list(defined_params.keys())
        
        # Сохраняем введенное значение
        current_param = param_keys[param_index]
        param_value = raw_text.strip() if raw_text.strip() else None
        
        # Если значение пустое, используем дефолтное
        if not param_value and isinstance(defined_params[current_param], dict):
            param_value = defined_params[current_param].get("default")
        
        state["params"][current_param] = param_value
        
        # Переходим к следующему параметру или запускаем отчет
        if param_index < len(param_keys) - 1:
            # Есть еще параметры - запрашиваем следующий
            state["param_index"] = param_index + 1
            next_param = param_keys[param_index + 1]
            param_info = defined_params.get(next_param, {})
            param_label = param_info.get("label", next_param) if isinstance(param_info, dict) else next_param
            param_type = param_info.get("type", "строка") if isinstance(param_info, dict) else "строка"
            param_default = param_info.get("default", "нет") if isinstance(param_info, dict) else "нет"
            
            prompt_text = (
                f"📝 **Ввод параметров для отчета '{state['job_name']}'**\n\n"
                f"Параметр {param_index + 2} из {len(param_keys)}: **{param_label}**\n"
                f"Тип: `{param_type}`, По умолчанию: `{param_default}`\n\n"
                f"Введите значение (или отправьте пустое сообщение для использования значения по умолчанию).\n"
                f"Для отмены введите /cancel"
            )
            
            requests.post(SEND_TEXT_URL, json={"chat_id": chat_id, "text": prompt_text}, headers=HEADERS, verify=False)
        else:
            # Все параметры введены - запускаем отчет
            job_name = state["job_name"]
            user_params = state["params"]
            
            # Очищаем состояние
            del user_states[user_id]
            
            execute_job(chat_id, job_name, user_params, user_id, display_name)
        return
    
    # 5. Обработка нажатия на кнопку (текст кнопки с эмодзи)
    if raw_text.startswith("📊"):
        # Убираем эмодзи и пробелы
        button_text = raw_text.replace("📊", "").strip()
        
        # Ищем отчет по названию
        jobs = get_all_jobs()
        found_job = None
        for job in jobs:
            job_title = get_job_title(job, JOBS_DIR)
            
            if button_text == job_title:
                found_job = job
                break
        
        # Если не нашли по названию, пробуем по техническому имени
        if not found_job and button_text in jobs:
            found_job = button_text
        
        if found_job:
            # Проверяем, требует ли отчет параметры
            job_config = load_job_config(found_job, JOBS_DIR)
            defined_params = job_config.get("parameters", {}) or {}
            require_params = job_config.get("require_parameters", False)
            
            param_keys = list(defined_params.keys())
            
            # Если параметры обязательны или есть параметры - запрашиваем ввод
            if len(param_keys) > 0:
                # Сохраняем состояние пользователя
                user_states[user_id] = {
                    "job_name": found_job,
                    "param_index": 0,
                    "params": {},
                    "defined_params": defined_params,
                    "require_params": require_params
                }
                
                # Запрашиваем первый параметр
                first_param = param_keys[0]
                param_info = defined_params.get(first_param, {})
                param_label = param_info.get("label", first_param) if isinstance(param_info, dict) else first_param
                param_type = param_info.get("type", "строка") if isinstance(param_info, dict) else "строка"
                param_default = param_info.get("default", "нет") if isinstance(param_info, dict) else "нет"
                
                prompt_text = (
                    f"📝 **Ввод параметров для отчета '{found_job}'**\n\n"
                    f"Параметр {1} из {len(param_keys)}: **{param_label}**\n"
                    f"Тип: `{param_type}`, По умолчанию: `{param_default}`\n\n"
                    f"Введите значение (или отправьте пустое сообщение для использования значения по умолчанию):"
                )
                
                requests.post(SEND_TEXT_URL, json={"chat_id": chat_id, "text": prompt_text}, headers=HEADERS, verify=False)
            else:
                # Параметров нет - запускаем сразу
                execute_job(chat_id, found_job, {}, user_id, display_name)
            return


def execute_job(chat_id, job_name, user_params, user_id=None, user_name=None):
    """Выполняет запуск отчета с заданными параметрами"""
    valid_jobs = get_all_jobs()
    
    if job_name not in valid_jobs:
        requests.post(SEND_TEXT_URL,
                      json={"chat_id": chat_id, "text": f"❓ Ошибка: Отчет '{job_name}' не найден в системе."},
                      headers=HEADERS, verify=False)
        return
    
    # Читаем config.yaml отчета
    job_config = load_job_config(job_name, JOBS_DIR)
    job_title = job_config.get("title", job_name)
    
    # Логируем начало запуска отчета
    if user_id and user_name:
        log_user_run(user_id, user_name, job_name, job_title, "started", user_params)
    
    # Инициализация дефолтных значений
    defined_params = job_config.get("parameters", {}) or {}
    require_params = job_config.get("require_parameters", False)
    
    param_keys = list(defined_params.keys())
    
    # Если параметры обязательны и не переданы - выводим ошибку
    if require_params and len(user_params) == 0 and len(param_keys) > 0:
        alert_text = (
            f"⚠️ **Ошибка запуска отчета '{job_name}'**\n\n"
            f"Этот отчет содержит конфиденциальные или объемные данные, "
            f"его **запрещено** запускать без параметров!\n\n"
            f"Пожалуйста, используйте текстовую команду с параметрами:\n"
            f"`run:{job_name} " + " ".join([f"[{k}]" for k in param_keys]) + "`"
        )
        requests.post(SEND_TEXT_URL, json={"chat_id": chat_id, "text": alert_text}, headers=HEADERS, verify=False)
        return
    
    # Формируем полные параметры с дефолтными значениями
    full_params = {}
    for k in param_keys:
        if k in user_params:
            full_params[k] = user_params[k]
        elif isinstance(defined_params[k], dict):
            full_params[k] = defined_params[k].get("default")
    
    # Отправляем уведомление о начале генерации
    requests.post(SEND_TEXT_URL, json={"chat_id": chat_id,
                                       "text": f"⏳ Запущен конвейер для отчета '{job_name}'...\nПараметры: {full_params}\nПодключаюсь к серверу БД. Пожалуйста, подождите."},
                  headers=HEADERS, verify=False)

    try:
        print(f"[DEBUG EXEC] Вызываем run_job('{job_name}', user_params={full_params})...")
        excel_path = run_job(job_name, user_params=full_params)

        print(f"[DEBUG EXEC] Функция run_job вернула значение: '{excel_path}'")
        if excel_path and os.path.exists(excel_path):
            print(f"[DEBUG EXEC] Размер файла на диске: {os.path.getsize(excel_path)} байт")
            file_name = os.path.basename(excel_path)
            print(f"[DEBUG EXEC] Подготовка к отправке файла: {file_name}")
            
            # Логируем успешное завершение
            if user_id and user_name:
                log_user_run(user_id, user_name, job_name, job_title, "success", full_params)

            # Читаем свежие настройки дистрибуции из config.yaml отчета
            send_to_chat = True
            nc_enabled = False
            nc_profile = "emias_kgu"
            nc_path = ""

            deliv = job_config.get("delivery", {})
            send_to_chat = deliv.get("send_to_chat", True)

            nc_cfg = deliv.get("nextcloud", {})
            nc_enabled = nc_cfg.get("enabled", False)
            nc_profile = nc_cfg.get("profile", "emias_kgu")
            nc_path = nc_cfg.get("remote_path", "").strip("/")

            # Формируем информативный текст статуса
            status_text = f"✅ **Отчет '{job_name}' успешно сформирован!**\n"
            if nc_enabled:
                status_text += f"☁️ *Файл выгружен в Nextcloud ({nc_profile}):* `{nc_path}/{file_name}`\n"

            if send_to_chat:
                status_text += "📎 *Файл прикреплен ниже:* "
                requests.post(SEND_TEXT_URL, json={"chat_id": chat_id, "text": status_text}, headers=HEADERS,
                              verify=False)

                file_headers = {"Authorization": f"OAuth {BOT_TOKEN}"}
                payload = {
                    "chat_id": str(chat_id),
                    "caption": f"✅ Отчет '{job_name}' успешно сформирован."
                }

                with open(excel_path, "rb") as f:
                    files = {
                        "document": (file_name, f,
                                     "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                    }

                    print(f"[DEBUG EXEC] Отправка проверенного Multipart на Яндекс...")
                    res = requests.post(
                        SEND_FILE_URL,
                        headers=file_headers,
                        data=payload,
                        files=files,
                        verify=False,
                        timeout=60
                    )

                print(f"[DEBUG EXEC] Ответ Яндекса: Статус {res.status_code}, Текст: {res.text}")

                if res.status_code != 200:
                    requests.post(SEND_TEXT_URL, json={"chat_id": chat_id,
                                                       "text": f"❌ Ошибка шлюза Яндекса при передаче файла:\n{res.text}"},
                                  headers=HEADERS, verify=False)
            else:
                status_text += "ℹ️ *Отправка файла напрямую в чат отключена в настройках отчета.*"
                requests.post(SEND_TEXT_URL, json={"chat_id": chat_id, "text": status_text}, headers=HEADERS,
                              verify=False)

            # После успешного выполнения показываем категории
            jobs = get_all_jobs()
            inline_keyboard = create_categories_keyboard(jobs)
            menu_text = "📋 **Доступные категории отчетов:**\n\nВыберите категорию для просмотра отчетов:"
            payload = {
                "chat_id": chat_id,
                "text": menu_text,
                "inline_keyboard": inline_keyboard
            }
            requests.post(SEND_TEXT_URL, json=payload, headers=HEADERS, verify=False)

    except Exception as e:
        print(f"[💥 ОШИБКА ГЕНЕРАЦИИ]: {e}")
        # Логируем ошибку
        if user_id and user_name:
            log_user_run(user_id, user_name, job_name, job_title, "error", full_params, str(e))
        requests.post(SEND_TEXT_URL, json={"chat_id": chat_id, "text": f"❌ Ошибка генерации отчета:\n{e}"},
                      headers=HEADERS, verify=False)


def start_pooling():
    print(f"[BOT] Бот @{BOT_USERNAME} успешно запущен на сервере. Режим: Кнопки (inline keyboard).")

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