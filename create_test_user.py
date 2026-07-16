import sqlite3
import bcrypt

# Путь к БД
DB_PATH = "data/job_status.db"

def create_test_user():
    """Создает тестового пользователя с захешированным паролелем."""
    
    # Используем bcrypt для streamlit_authenticator
    password = "admin123"
    password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Проверяем существование таблицы users
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        if not cursor.fetchone():
            print("Создаем таблицу users...")
            cursor.execute("""
                CREATE TABLE users (
                    username TEXT PRIMARY KEY,
                    name TEXT,
                    password_hash TEXT,
                    yandex_id TEXT,
                    display_name TEXT,
                    is_active INTEGER DEFAULT 0
                )
            """)
        
        # Проверяем существование пользователя
        cursor.execute("SELECT username FROM users WHERE username = ?", ("admin",))
        if cursor.fetchone():
            print("Пользователь 'admin' уже существует. Обновляем пароль...")
            cursor.execute("UPDATE users SET password_hash = ? WHERE username = ?", (password_hash, "admin"))
        else:
            print("Создаем пользователя 'admin'...")
            cursor.execute("""
                INSERT INTO users (username, name, password_hash, yandex_id, display_name, is_active)
                VALUES (?, ?, ?, ?, ?, ?)
            """, ("admin", "Администратор", password_hash, "test_id", "Admin User", 1))
        
        conn.commit()
        print("[OK] User 'admin' created/updated")
        print(f"   Login: admin")
        print(f"   Password: {password}")
        print(f"   Hash: {password_hash}")
        
    except Exception as e:
        print(f"[ERROR] {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    create_test_user()
