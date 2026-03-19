import asyncio
import sqlite3
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from geopy.distance import geodesic
from numpy.version import full_version

from Registration import Registration

from dotenv import load_dotenv
import os
# Token
load_dotenv("token.env")
TOKEN = os.getenv("TOKEN")

# Settings
bot = Bot(token=TOKEN)
dp = Dispatcher()
OFFICE_COORDS_POL = (28.092451, -16.723255) # Work coordinates
OFFICE_COORDS2 = (28.239078, -16.797467)    # Coordinates for verification
MAX_DISTANCE = 100
ADMIN_IDS = [1366979749]

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
            checkin_time TEXT,
            checkout_time TEXT
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
        await message.answer("👋 Пожалуйста, введите свое имя и фамилию.")

    elif role == "pending":
        """Жде на доступ"""
        await message.answer("⏳")


@dp.message(Registration.waiting_for_name)
async def process_registration_name(message: types.Message, state: FSMContext):
    """Captures the name during registration and saves it in the database."""
    full_name = message.text
    user_id = message.from_user.id

    # Записуємо з роллю "pending"
    conn = sqlite3.connect("DataBase/office.db")
    cursor = conn.cursor()
    cursor.execute('INSERT INTO employees (user_id, full_name, role) VALUES (?,?,?)', (user_id,full_name,"worker"))
    conn.commit()
    conn.close()

    # Turn off standby mode
    await message.answer(f"{full_name} Saved!")
    btn_location = KeyboardButton(text="📍 Отметиться на работе", request_location=True)
    btn_checkout = KeyboardButton(text="🔴 Уйти с работы")
    btn_cabinet = KeyboardButton(text="👤 Мой кабинет")
    keyboard = ReplyKeyboardMarkup(keyboard=[[btn_location, btn_checkout], [btn_cabinet]], resize_keyboard=True)
    await message.answer(
        f"✅ {full_name}! Регистрация успешна.\nРабочее меню открыто, можешь отмечаться!",
        reply_markup=keyboard
    )
    await state.clear()

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
    distance2 = geodesic(OFFICE_COORDS_POL, user_coords).meters

    if distance <= MAX_DISTANCE or distance2 <= MAX_DISTANCE:
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        conn = sqlite3.connect('DataBase/office.db')
        cursor = conn.cursor()
        cursor.execute('SELECT id, checkout_time FROM checkins WHERE user_id = ? ORDER BY id DESC LIMIT 1', (user_id,))
        last_record = cursor.fetchone()
        if last_record and last_record[1] is None:
            await message.answer(f" Ты уже на работе! Чтобы завершить смену, нажми кнопку '🔴 Уйти с работы")
        # Якщо відкритої зміни не має
        else:
            # Створюємо новий запис про прихід
            cursor.execute('SELECT full_name FROM employees WHERE user_id = ?', (user_id,))
            full_name = cursor.fetchone()[0]
            cursor.execute('INSERT INTO checkins (user_id, full_name, checkin_time) VALUES (?, ?, ?)',
                           (user_id, full_name, current_time))
            conn.commit()
            await message.answer(f"Смена успешно начата!\nВремя прихода: {current_time}")
            conn.close()
    else:
        await message.answer(f"❌ Отказ! Ты слишком далеко ({int(distance)} м).")

@dp.message(F.text == "🔴 Уйти с работы")
async def handle_checkout(message: types.Message):
    user_id = message.from_user.id
    role = get_user_role(user_id)
    if role not in ["worker","admin"]:
        return
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = sqlite3.connect('DataBase/office.db')
    cursor = conn.cursor()

    # Шукаємо останній запис користувача
    cursor.execute('SELECT id, checkout_time FROM checkins WHERE user_id = ? ORDER BY id DESC LIMIT 1', (user_id,))
    last_record = cursor.fetchone()

    # Сувора перевірка: чи є відкрита зміна для закриття?
    if last_record and last_record[1] is None:
        record_id = last_record[0]
        cursor.execute('UPDATE checkins SET checkout_time = ? WHERE id = ?', (current_time, record_id))
        conn.commit()
        await message.answer(f"🔴 Изменение успешно завершено!\nВремя ухода: {current_time}")
    else:
        # Відхиляємо дію, якщо людина не відмітила прихід
        await message.answer("❌ Отказ! У тебя нет открытого изменения. Сначала отмитесь о приходе.")

    conn.close()


@dp.message(F.text == "👤 Мой кабинет")
async def my_cabinet(message: types.Message):
    """Показує 5 останніх відміток."""
    user_id = message.from_user.id
    role = get_user_role(user_id)

    if role not in ["worker", "admin"]:
        return  # Ігноруємо натискання, якщо немає прав

    conn = sqlite3.connect('DataBase/office.db')
    cursor = conn.cursor()
    cursor.execute('SELECT checkin_time FROM checkins WHERE user_id = ? ORDER BY id DESC LIMIT 5', (user_id,))
    records = cursor.fetchall()
    conn.close()

    if records:
        text = "👤 **Твой кабинет**\n\nПоследние отметки:\n"
        for row in records:
            text += f"🕒 {row[0]}\n"
        await message.answer(text, parse_mode="Markdown")
    else:
        await message.answer("У тебя еще нет отметок.")


@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    """Секретна адмін-панель зі зведенням за сьогоднішній день."""

    # 1. Перевірка параметра прав доступу
    if message.from_user.id not in ADMIN_IDS:
        return

    # 2. Отримуємо параметр сьогоднішньої дати (наприклад, "2026-03-16")
    today_date = datetime.now().strftime("%Y-%m-%d")

    conn = sqlite3.connect('DataBase/office.db')
    cursor = conn.cursor()

    # 3. Робимо вибірку з бази виключно за поточний день
    # Оператор LIKE шукає всі записи, які ПОЧИНАЮТЬСЯ з сьогоднішньої дати
    cursor.execute('''
        SELECT full_name, checkin_time, checkout_time 
        FROM checkins 
        WHERE checkin_time LIKE ?
        ORDER BY checkin_time ASC
    ''', (f"{today_date}%",))

    today_records = cursor.fetchall()
    conn.close()

    # 4. Формуємо красивий текст звіту
    text = f"👑 **Админ-панель**\n\n📅 **Отчет за сегодня ({today_date}):**\n\n"

    if today_records:
        for row in today_records:
            name = row[0]
            # Відрізаємо дату, залишаємо тільки час (наприклад, "09:15:00")
            checkin = row[1].split()[1]

            # Перевіряємо параметр уходу
            if row[2] is None:
                status = "🟢 На работе"
            else:
                checkout = row[2].split()[1]
                status = f"🔴 Пошел в {checkout}"

            text += f"👤 **{name}**\n   ├ Приход: {checkin}\n   └ {status}\n\n"
    else:
        text += "📭 Сегодня еще никто не отметился.\n"

    # Залишаємо кнопку "Завантажити звіт" на майбутнє
    btn_report = InlineKeyboardButton(text="📥 Загрузить отчет (Excel)", callback_data="get_report")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[btn_report]])

    await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")


@dp.message(Command("approve"))
async def approve_user(message: types.Message):
    """Адмінська команда для підтвердження працівника. Формат: /approve 123456789"""

    # 1. Перевіряємо, чи цю команду пише саме адміністратор
    if message.from_user.id not in ADMIN_IDS:
        return  # Якщо це звичайний користувач - просто ігноруємо
    try:
        target_user_id = int(message.text.split()[1])
    except (IndexError, ValueError):
        await message.answer("❌ Неправильний формат.\nНапиши команду так: /approve ID_користувача")
        return

    conn = sqlite3.connect('DataBase/office.db')
    cursor = conn.cursor()

    cursor.execute('SELECT full_name FROM employees WHERE user_id = ?', (target_user_id,))
    user_data = cursor.fetchone()

    if user_data:
        cursor.execute("UPDATE employees SET role = 'worker' WHERE user_id = ?", (target_user_id,))
        conn.commit()

        await message.answer(f"✅ Працівника {user_data[0]} успішно підтверджено!\nПараметр змінено на 'worker'.")

        try:
            await bot.send_message(target_user_id,
                                   "🎉 Керівник підтвердив ваш профіль!\nНатисніть /start, щоб відкрити робоче меню.")
        except Exception:
            pass  # Якщо щось пішло не так (наприклад, людина видалила чат), бот не зламається

    else:
        await message.answer("❌ Користувача з таким ID не знайдено в базі.")

    conn.close()


async def main():
    init_db()
    print("Бот запущений! База даних працює.")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
