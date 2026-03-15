import asyncio
import sqlite3
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from geopy.distance import geodesic
from Registration import Registration

# Settings
TOKEN = "8653019757:AAEzAS7UQrf7e1hoE6gPtpZs6HwKP0r2yRY"
bot = Bot(token=TOKEN)
dp = Dispatcher()
OFFICE_COORDS_POL = (28.092451, -16.723255) # Work coordinates
OFFICE_COORDS2 = (28.239078, -16.797467)    # Coordinates for verification
MAX_DISTANCE = 100
ADMIN_ID = [1366979749]

# --- Data base---
def init_db():
    """Creates a database file and table if they do not already exist."""
    conn = sqlite3.connect('DataBase/office.db')
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

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS employees(
            user_id INTEGER PRIMARY KEY,
            full_name TEXT,
            role TEXT
        )
    ''')
    conn.commit()
    conn.close()

def get_user_role(user_id):
    """Helper function: gets the user role from the database"""
    conn = sqlite3.connect('DataBase/office.db')
    cursor = conn.cursor()
    cursor.execute('SELECT role FROM employees WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

# ---- Bot -----

@dp.message(CommandStart())
async def start_cmd(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    role = get_user_role(user_id)

    if role is None:
        """ Нова решістрація"""
        await state.set_state(Registration.waiting_for_name)
        await message.answer("👋 Congratulations! You are a new employee. \nPlease enter your First and Last Name.")

    elif role == "pending":
        """Жде на доступ"""
        await message.answer("⏳ Your application is being reviewed by the administrator. Please wait for confirmation.")

    elif role == "worker" or role == "admin":
        btn_location = KeyboardButton(text="📍 Відмітитися на роботі", request_location=True)
        btn_cabinet = KeyboardButton(text="👤 Мій кабінет")
        keyboard = ReplyKeyboardMarkup(keyboard=[[btn_location], [btn_cabinet]], resize_keyboard=True)
        await message.answer(f"Main window open, {message.from_user.first_name}!", reply_markup=keyboard)

@dp.message(Registration.waiting_for_name)
async def process_registration_name(message: types.Message, state: FSMContext):
    """Captures the name during registration and saves it in the database."""
    full_name = message.text
    user_id = message.from_user.id

    # Записуємо з роллю "pending"
    conn = sqlite3.connect("DataBase/office.db")
    cursor = conn.cursor()
    cursor.execute('INSERT INTO employees (user_id, full_name, role) VALUES (?,?,?)', (user_id,full_name,"pending"))
    conn.commit()
    conn.close()

    # Turn off standby mode
    await state.clear()
    await message.answer(f"{full_name} Saved!")

@dp.message(F.location)
async def handle_location(message: types.Message):
    """Checks the distance and makes a mark in the database."""
    user_id = message.from_user.id
    role = get_user_role(user_id)

    if role not in ["worker","admin"]:
        await message.answer("You do not have permission to mark.")
        return

    user_coords = (message.location.latitude, message.location.longitude)
    distance = geodesic(OFFICE_COORDS2, user_coords).meters
    # Головна умова запису: дистанція має бути в межах норми
    if distance <= MAX_DISTANCE:
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Дістаємо ім'я з бази працівників, щоб красиво записати в історію
        conn = sqlite3.connect('office.db')
        cursor = conn.cursor()
        cursor.execute('SELECT full_name FROM employees WHERE user_id = ?', (user_id,))
        full_name = cursor.fetchone()[0]

        # Робимо запис про успішний прихід
        cursor.execute('INSERT INTO checkins (user_id, full_name, checkin_time) VALUES (?, ?, ?)',
                       (user_id, full_name, current_time))
        conn.commit()
        conn.close()

        await message.answer(f"✅ Успішно! Ти на роботі.\nЧас: {current_time}")
    else:
        await message.answer(f"❌ Відмова! Ти занадто далеко ({int(distance)} м).\nПідійди ближче.")


@dp.message(F.text == "👤 Мій кабінет")
async def my_cabinet(message: types.Message):
    """Показує 5 останніх відміток."""
    user_id = message.from_user.id
    role = get_user_role(user_id)

    if role not in ["worker", "admin"]:
        return  # Ігноруємо натискання, якщо немає прав

    conn = sqlite3.connect('office.db')
    cursor = conn.cursor()
    cursor.execute('SELECT checkin_time FROM checkins WHERE user_id = ? ORDER BY id DESC LIMIT 5', (user_id,))
    records = cursor.fetchall()
    conn.close()

    if records:
        text = "👤 **Твій кабінет**\n\nОстанні відмітки:\n"
        for row in records:
            text += f"🕒 {row[0]}\n"
        await message.answer(text, parse_mode="Markdown")
    else:
        await message.answer("У тебе ще немає відміток.")


@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    """Секретна адмін-панель."""
    if message.from_user.id in ADMIN_IDS:
        btn_report = InlineKeyboardButton(text="📥 Завантажити звіт", callback_data="get_report")
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[btn_report]])

        await message.answer("👑 **Адмін-панель**", reply_markup=keyboard)


# --- 🚀 5. ЗАПУСК БОТА ---
async def main():
    init_db()
    print("Бот запущений! База даних працює.")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
