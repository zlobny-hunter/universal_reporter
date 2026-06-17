import streamlit as st
import pandas as pd
import sqlite3
import os
import yaml
import datetime
import streamlit_authenticator as stauth

# Импортируем готовые функции из нашего ядра
from src.main import run_job, get_all_jobs
from src.utils.config_loader import setup_logging

# Инициализируем базовое логирование системы, чтобы логи ручного запуска тоже писались
setup_logging()

# Настройка конфигурации веб-страницы в браузере
st.set_page_config(
    page_title="Универсальный Отчетник",
    page_icon="📊",
    layout="wide"
)


# --- 1. ЗАГРУЗКА ПОЛЬЗОВАТЕЛЕЙ ИЗ ТАБЛИЦЫ ---
def load_users_from_db():
    conn = sqlite3.connect("data/job_status.db")  # Укажите ваш актуальный путь к БД
    cursor = conn.cursor()
    cursor.execute("SELECT username, name, password_hash FROM users")
    rows = cursor.fetchall()
    conn.close()

    # Формируем структуру словаря, которую требует streamlit-authenticator
    credentials = {"usernames": {}}
    for username, name, password_hash in rows:
        credentials["usernames"][username] = {
            "name": name,
            "password": password_hash
        }
    return credentials


credentials = load_users_from_db()

# --- 2. ИНИЦИАЛИЗАЦИЯ АУТЕНТИФИКАТОРА ---
authenticator = stauth.Authenticate(
    credentials=credentials,
    cookie_name="report_system_cookie",  # Имя куки для запоминания сессии
    key="super_secret_cookie_key",  # Любой случайный ключ для шифрования куки
    cookie_expiry_days=30  # Сколько дней помнить пользователя
)

# --- 3. ОТРЕНДЕРИТЬ ФОРМУ ВХОДА ---
authenticator.login(location='main', fields={
    'Form name': 'Авторизация в системе отчетов',
    'Username': 'Логин',
    'Password': 'Пароль',
    'Login': 'Войти'
})

# --- 4. ЖЕСТКАЯ ПРОВЕРКА СТАТУСА ---

# Сценарий А: Пользователь ввел НЕВЕРНЫЕ данные
if st.session_state.get('authentication_status') == False:
    st.error('Неверный логин или пароль')
    st.stop()  # Хватит! Дальше код не выполняем, прячем интерфейс

# Сценарий Б: Форма пустая (пользователь еще ничего не вводил)
elif st.session_state.get('authentication_status') == None:
    st.warning('Пожалуйста, введите логин и пароль')
    st.stop()  # Хватит! Ждем ввода данных, прячем интерфейс

# Сценарий В: УСПЕШНЫЙ ВХОД
elif st.session_state.get('authentication_status') == True:

    # Достаем имя пользователя для приветствия
    user_name = st.session_state.get('name', 'Пользователь')

    # Кнопка "Выйти" в сайдбар
    with st.sidebar:
        st.write(f"Привет, **{user_name}**!")
        authenticator.logout('Выйти из системы', 'sidebar')
        st.write("---")


# ... дальше идут ваши таблицы, селекты дат, кнопка запуска конвейера ...
st.title("📊 Панель управления системой отчетов v1.0")
st.markdown("Здесь вы можете отслеживать статус автоматических задач и запускать отчеты вручную.")

DB_PATH = "data/job_status.db"

def load_statuses_from_db():
    """Читает историю запусков из SQLite и возвращает Pandas DataFrame"""
    if not os.path.exists(DB_PATH):
        return pd.DataFrame(columns=["Отчет", "Последний запуск", "Статус", "Описание ошибки"])
    
    try:
        conn = sqlite3.connect(DB_PATH)
        query = """
            SELECT job_name as 'Отчет', 
                   job_title as 'Полное имя отчета',
                   run_time as 'Последний запуск', 
                   status as 'Статус', 
                   error_message as 'Описание ошибки'
            FROM job_runs
            ORDER BY run_time DESC
        """
        df = pd.read_sql(query, conn)
        conn.close()
        return df
    except Exception as e:
        st.error(f"Ошибка чтения базы данных истории: {e}")
        return pd.DataFrame()

# --- БЛОК 1: МОНИТОР СТАТУСОВ ---
st.subheader("📋 Состояние и история задач")

df_statuses = load_statuses_from_db()

if df_statuses.empty:
    st.info("История запусков в базе данных пока пуста. Запустите отчет для генерации статуса.")
else:
    # Функция для красивой подсветки строк в зависимости от статуса отчета
    def color_status(val):
        if val == "Успешно":
            return "background-color: #d4edda; color: #155724; font-weight: bold;"
        elif val == "Ошибка":
            return "background-color: #f8d7da; color: #721c24; font-weight: bold;"
        elif "Пропущен" in str(val):
            return "background-color: #fff3cd; color: #856404;"
        return ""

    # Применяем стили к колонке "Статус" и выводим интерактивную таблицу
    styled_df = df_statuses.style.map(color_status, subset=["Статус"])
    #st.dataframe(styled_df, use_container_width=True, hide_index=True)
    st.dataframe(styled_df, width="stretch", hide_index=True)

st.markdown("---")

# --- БЛОК 2: УМНЫЙ РУЧНОЙ ЗАПУСК ---
st.subheader("🚀 Запуск задачи вручную")

available_jobs = get_all_jobs()

if not available_jobs:
    st.warning("В папке 'jobs/' не найдено ни одного отчета.")
else:
    selected_job = st.selectbox("Выберите необходимый отчет из списка:", available_jobs)
    
    # Читаем конфиг выбранного отчета, чтобы узнать, нужны ли ему параметры
    job_config_path = os.path.join("jobs", selected_job, "config.yaml")
    has_parameters = False
    param_decl = {}
    
    if os.path.exists(job_config_path):
        with open(job_config_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
            param_decl = cfg.get("parameters", {})
            has_parameters = bool(param_decl)

    # Контейнер для динамических полей ввода
    ui_params = {}
    
    if has_parameters:
        st.info("ℹ️ Этот отчет требует указания параметров для сборки:")

        # Генерируем виджеты на основе декларации в config.yaml
        for p_name, p_info in param_decl.items():
            p_type = p_info.get("type")
            p_label = p_info.get("label", p_name)

            if p_type == "date":
                # Рассчитываем границы для календаря
                if "birth" in p_name or "birth" in p_label.lower():
                    min_date = datetime.date(1920, 1, 1)
                    default_value = datetime.date(1990, 1, 1)
                else:
                    min_date = datetime.date(2000, 1, 1)
                    default_value = datetime.date.today()

                max_date = datetime.date.today()

                # Рендерим виджет ВНУТРИ условия и сохраняем значение в ui_params!
                ui_params[p_name] = st.date_input(
                    label=f"📅 {p_label}:",
                    value=default_value,
                    min_value=min_date,
                    max_value=max_date,
                    key=p_name
                )

            elif p_type == "int_list":
                raw_list = st.text_input(f"🔢 {p_label} ({p_name}, через запятую):", "101, 102")
                # Сразу конвертируем в кортеж для SQL
                ui_params[p_name] = tuple(int(x.strip()) for x in raw_list.split(",") if x.strip().isdigit())
    else:
        st.success("✨ Этот отчет является статическим. Параметры не требуются.")

    # Кнопка запуска
    btn_run = st.button("Запустить отчет", type="primary")
        
    if btn_run:
        with st.spinner(f"Выполняется конвейер для отчета '{selected_job}'..."):
            try:
                # Форматируем даты из виджетов Streamlit в строки для SQL
                formatted_params = {}
                for k, v in ui_params.items():
                    if isinstance(v, datetime.date):
                        # Если это дата начала, даем время 00:00, если конца — 23:59 для точности фильтра
                        if "start" in k:
                            formatted_params[k] = v.strftime("%Y-%m-%d 00:00:00")
                        else:
                            formatted_params[k] = v.strftime("%Y-%m-%d 23:59:59")
                    else:
                        formatted_params[k] = v

                # Передаем параметры (или None, если отчет статический)
                # Если мы попытаемся передать параметры туда, где их нет, 
                # оркестратор выкинет ValueError, и мы безопасно покажем её пользователю.
                run_job(selected_job, external_params=formatted_params if has_parameters else None)
                
                st.success(f"🎉 Отчет '{selected_job}' успешно выполнен!")
                st.rerun()
                
            except Exception as e:
                # Выводим ошибку валидации или СУБД прямо в красивое красное окно UI
                st.error(f"❌ Ошибка выполнения конвейера: {e}")