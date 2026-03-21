from aiogram.fsm.state import State, StatesGroup
import sqlite3

class Registration(StatesGroup):
    waiting_for_name = State()


class RegistrationNewUsers:
    def __init__(self,users= 'DataBase/users.db'):
        self.users_db = users
        self.rigistration_new_user()


    def rigistration_new_user(self):
        conn = sqlite3.connect(self.users_db)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                last_name TEXT
            )
        """)
        conn.commit()
        conn.close()

    def user_exists(self,telegram_id: int) -> bool:
        """Перевірка на існування користувача в базі даних по його телеграм id"""
        conn = sqlite3.connect(self.users_db)
        cursor = conn.cursor()

        cursor.execute("SELECT 1 FROM users WHERE telegram_id = ?",(telegram_id))
        result = cursor.fetchone()
        conn.close()
        return result is not None

    def add_user(self, telegram_id: int, name: str, last_name: str = ""):
        """Додаємо користувача за умови що його не має в базі"""
        if not self.user_exists(telegram_id):
            conn = sqlite3.connect(self.users_db)
            cursor = conn.cursor()
            cursor.execute("INSERT INTO users (telegram_id,name, last_name) VALUES (?,?,?)",(telegram_id,name,last_name))
            conn.commit()
            conn.close()
            return True # Успішно додано
        return False  #Вже існує користувач
