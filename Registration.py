from aiogram.fsm.state import State, StatesGroup
import sqlite3

class Registration(StatesGroup):

    waiting_for_name = State()

    @staticmethod
    def rigistration_new_user():
        conn = sqlite3.connect("users.db")
        cursor = conn.cursor()

        cursor.execute("""
            CRETATE TABLE IF NOT EXISTS users(
                id INTEGER PRIMARY KAY AUTOINKREMENT,
                name TEXT,
                last_name TEXT
            )
        """)


