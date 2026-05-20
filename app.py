import streamlit as st
import pandas as pd
import sqlite3
import os

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

st.title("📊 Панель управления системой отчетов")
st.markdown("Здесь вы можете отслеживать статус автоматических задач и запускать отчеты вручную.")

DB_PATH = "data/run_history.db"

def load_statuses_from_db():
    """Читает историю запусков из SQLite и возвращает Pandas DataFrame"""
    if not os.path.exists(DB_PATH):
        return pd.DataFrame(columns=["Отчет", "Последний запуск", "Статус", "Описание ошибки"])
    
    try:
        conn = sqlite3.connect(DB_PATH)
        query = """
            SELECT job_name as 'Отчет', 
                   last_run as 'Последний запуск', 
                   status as 'Статус', 
                   error_message as 'Описание ошибки'
            FROM job_states
            ORDER BY last_run DESC
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
    st.dataframe(styled_df, use_container_width=True, hide_index=True)

st.markdown("---")

# В app.py в блоке ручного запуска добавляем интерфейс параметров:
import datetime

st.subheader("🚀 Принудительный ручной запуск с параметрами")

# 1. Виджеты календаря
col_d1, col_d2 = st.columns(2)
with col_d1:
    user_start = st.date_input("Дата начала:", datetime.date.today() - datetime.timedelta(days=7))
with col_d2:
    user_end = st.date_input("Дата окончания:", datetime.date.today())

# 2. Текстовое поле для ввода номеров рецептов через запятую
recipes_str = st.text_input("Номера рецептов (через запятую):", "101, 102, 105")

if st.button("Запустить с параметрами"):
    # Преобразуем строку "101, 102" в чистый кортеж чисел (101, 102) для SQL оператора IN
    try:
        recipes_tuple = tuple(int(x.strip()) for x in recipes_str.split(",") if x.strip().isdigit())
    except ValueError:
        recipes_tuple = ()

    # Собираем параметры в упакованный пакет
    live_params = {
        "date_start": f"{user_start} 00:00:00",
        "date_end": f"{user_end} 23:59:59",
        "recipe_list": recipes_tuple
    }
    
    # Чтобы передать эти параметры в run_job, достаточно немного расширить сигнатуру run_job(job_name, params=None) в src/main.py
    with st.spinner("Сборка кастомного отчета..."):
        # Передаем параметры напрямую в оркестратор
        run_job(selected_job, custom_params=live_params)
        st.success("Отчет сгенерирован по вашим фильтрам!")