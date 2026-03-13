import asyncio
import sqlite3
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from geopy.distance import geodesic

# Settings
TOKEN = "8653019757:AAEzAS7UQrf7e1hoE6gPtpZs6HwKP0r2yRY"
OFFICE_COORDS_POL = (28.092451, -16.723255) # Work coordinates
OFFICE_COORDS2 = (28.239078, -16.797467)    # Coordinates for verification
MAX_DISTANCE = 100
ADMIN_ID = 3609

# --- Data base---
def init_db():
    """Creates a database file and table if they do not already exist."""
    conn = sqlite3.connect('office.db')
    cursor = conn.cursor()
    # Create a table: Record ID, User ID, Name, Arrival Time
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS checkins(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        full_name TEXT,
        checkin_time TEXT
        )
    ''')
    conn.commit()
    conn.close()

@dp.message(CommandStart())
async def start_cmd(message: type.Message):
    """Triggered when the bot starts. Shows the main menu."""
    btn_location = KeyboardButton(text = "Stand out at work")
    btn_cabinet = KeyboardButton(text = "My office")

    keyboard = ReplyKeyboardMarkup(keyboard=[[btn_location], [btn_cabinet]],resize_keyboard=True)

    await message.answer(f"Hello {message.from_user.first_name} \nSelect an action from the menu below: ", reply_markup=keyboard)

