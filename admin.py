import sqlite3
import streamlit_authenticator as stauth

# Исправленный вызов: явно указываем passwords=
hashed_password = stauth.Hasher.hash('admin123')

# Дальше ваш код без изменений
conn = sqlite3.connect("data/job_status.db")
cursor = conn.cursor()
cursor.execute(
    "INSERT OR REPLACE INTO users (username, name, password_hash) VALUES (?, ?, ?)",
    ("admin", "Admin", hashed_password)
)
conn.commit()
conn.close()
print("Пользователь успешно создан!")