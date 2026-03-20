from aiogram.fsm.state import State, StatesGroup
import sqlite3

class Registration(StatesGroup):
    waiting_for_name = State()


class RegistrationNewUsers:
    def __init__(self,users= 'DataBase/users.db'):
        self.users = users


    def rigistration_new_user(self):
        conn = sqlite3.connect(self.users)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                last_name TEXT
            )
        """)


