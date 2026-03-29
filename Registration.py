from aiogram.fsm.state import State, StatesGroup
import sqlite3

class Registration(StatesGroup):
    waiting_for_name = State()

class RegistrationNewUsers:
    def __init__(self, db_path='DataBase/office.db'): # Використовуємо одну БД
        self.db_path = db_path
        self.init_table()

    def init_table(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        # Додаємо telegram_id, бо він потрібен для перевірки
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE,
                name TEXT,
                last_name TEXT
            )
        """)
        conn.commit()
        conn.close()

    def user_exists(self, telegram_id: int) -> bool:
        """Перевірка, чи є користувач у таблиці employees."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        # Кома (telegram_id,) обов'язкова для створення кортежу
        cursor.execute("SELECT 1 FROM employees WHERE user_id = ?", (telegram_id,))
        result = cursor.fetchone()
        conn.close()
        return result is not None