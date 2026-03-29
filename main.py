import asyncio
import sqlite3
import os
from datetime import datetime
from dotenv import load_dotenv
import calendar

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from geopy.distance import geodesic

# Імпортуємо виправлені класи
from Registration import RegistrationNewUsers, Registration

# Завантаження токена
load_dotenv("token.env")
TOKEN = os.getenv("TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Налаштування координат
OFFICE_COORDS_POL = (28.092451, -16.723255)
OFFICE_COORDS2 = (28.239078, -16.797467)
MAX_DISTANCE = 100
ADMIN_IDS = [1366979749]

db_users = RegistrationNewUsers()


def init_db():
    """
    toctree::
    :maxdepth: 2
    :caption:
        Ініціалізація бази даних при старті бота.
        1. Перевірка наявносі директорії DataBase. Якщо її немає - створює.
        2. Підключається до файлу 'office.db' (або створює)
        3. Створює таблицю 'checkins' для фіксації робочого часу(id, користувач, час початку, час завершення)
        4. Створює таблицю ''employees' для збереження списку працівників.:
        :return
    """
    # Перевірка та створення папки для бази даних
    if not os.path.exists('DataBase'):
        os.makedirs('DataBase')

    # підключення до бази даних
    conn = sqlite3.connect('DataBase/office.db')
    cursor = conn.cursor()

    # Створення таблиці відміток часу(якщо не існує)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS checkins(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            full_name TEXT,
            checkin_time TEXT,
            checkout_time TEXT
        )
    ''')
    # Створення таблиці співробітників
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS employees(
            user_id INTEGER PRIMARY KEY,
            full_name TEXT,
            role TEXT
        )
    ''')
    # Збереження змін та закриття з'єднання
    conn.commit()
    conn.close()


def get_user_role(user_id):
    """
        Функція є допоміжною, для перевірки прав доступу
        Отримує роль працівника з бази даних за його Telegram ID.
        user_id (int): Унікальний індефікатор користувача
        Повертає str | None: Роль користувача, None якщо не зареєстрований
        :return
    """
    conn = sqlite3.connect('DataBase/office.db')
    cursor = conn.cursor()

    # Пошук ролі для конкретного user_id
    # Використовуємо параметризований запит (?) для беспеки, sql-інєкцій
    cursor.execute('SELECT role FROM employees WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()

    # Якщо користувача знайдено (result не порожній) повертається нульовий елемент кортежу
    return result[0] if result else None


def get_main_keyboard():
    """

        :return
    """
    btn_location = KeyboardButton(text="📍 Отметиться на работе", request_location=True)
    btn_checkout = KeyboardButton(text="🔴 Уйти с работы")
    btn_cabinet = KeyboardButton(text="👤 Мой кабинет")
    return ReplyKeyboardMarkup(keyboard=[[btn_location, btn_checkout], [btn_cabinet]], resize_keyboard=True)


# --- Обробники ---

@dp.message(CommandStart())
async def start_cmd(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if db_users.user_exists(user_id):
        await message.answer("Твой кабинет готов к работе", reply_markup=get_main_keyboard())
    else:
        await state.set_state(Registration.waiting_for_name)
        await message.answer("Введи имя и фамилию для регистрации:")


@dp.message(Registration.waiting_for_name)
async def process_registration_name(message: types.Message, state: FSMContext):
    full_name = message.text
    user_id = message.from_user.id

    conn = sqlite3.connect("DataBase/office.db")
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO employees (user_id, full_name, role) VALUES (?,?,?)',
                   (user_id, full_name, "worker"))
    conn.commit()
    conn.close()

    await message.answer(f"✅ Регистрация успешна, {full_name}!", reply_markup=get_main_keyboard())
    await state.clear()


@dp.message(F.location)
async def handle_location(message: types.Message):
    user_id = message.from_user.id
    role = get_user_role(user_id)

    if not role:
        await message.answer("Вы не зарегистрированы.")
        return

    user_coords = (message.location.latitude, message.location.longitude)
    dist1 = geodesic(OFFICE_COORDS2, user_coords).meters
    dist2 = geodesic(OFFICE_COORDS_POL, user_coords).meters

    if dist1 <= MAX_DISTANCE or dist2 <= MAX_DISTANCE:
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with sqlite3.connect('DataBase/office.db') as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT id, checkout_time FROM checkins WHERE user_id = ? ORDER BY id DESC LIMIT 1', (user_id,))
            last_record = cursor.fetchone()

            if last_record and last_record[1] is None:
                await message.answer("Ты уже на работе! Чтобы закончить, нажми '🔴 Уйти с работы'")
            else:
                cursor.execute('SELECT full_name FROM employees WHERE user_id = ?', (user_id,))
                full_name = cursor.fetchone()[0]
                cursor.execute('INSERT INTO checkins (user_id, full_name, checkin_time) VALUES (?, ?, ?)',
                               (user_id, full_name, current_time))
                conn.commit()
                await message.answer(f"🚀 Смена начата!\nВремя: {current_time}")
    else:
        min_dist = int(min(dist1, dist2))
        await message.answer(f"❌ Слишком далеко ({min_dist} м от офиса).")


@dp.message(F.text == "🔴 Уйти с работы")
async def handle_checkout(message: types.Message):
    user_id = message.from_user.id
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with sqlite3.connect('DataBase/office.db') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT id, checkout_time FROM checkins WHERE user_id = ? ORDER BY id DESC LIMIT 1', (user_id,))
        last_record = cursor.fetchone()

        if last_record and last_record[1] is None:
            cursor.execute('UPDATE checkins SET checkout_time = ? WHERE id = ?', (current_time, last_record[0]))
            conn.commit()
            await message.answer(f"🔴 Смена завершена!\nВремя: {current_time}")
        else:
            await message.answer("❌ У тебя нет открытой смены.")


@dp.message(F.text == "👤 Мой кабинет")
async def my_cabinet(message: types.Message):
    user_id = message.from_user.id
    now = datetime.now()
    day = now.day

    # 1. Визначаємо початок поточного звітного періоду
    if day <= 15:
        # Період з 1 по 15 число
        period_start = now.replace(day=1, hour=0, minute=0, second=0).strftime("%Y-%m-%d %H:%M:%S")
        period_name = f"с 01 по 15 {now.strftime('%B')}"
    else:
        # Період з 16 по 30/31 число
        period_start = now.replace(day=16, hour=0, minute=0, second=0).strftime("%Y-%m-%d %H:%M:%S")
        period_name = f"с 16 по конец {now.strftime('%B')}"

    with sqlite3.connect('DataBase/office.db') as conn:
        cursor = conn.cursor()

        # 2. Рахуємо кількість унікальних днів (DATE(checkin_time)), коли були записи
        cursor.execute('''
            SELECT COUNT(DISTINCT DATE(checkin_time)) 
            FROM checkins 
            WHERE user_id = ? AND checkin_time >= ?
        ''', (user_id, period_start))

        days_worked = cursor.fetchone()[0]

        # 3. Отримуємо останні 5 записів для списку
        cursor.execute('''
            SELECT checkin_time, checkout_time 
            FROM checkins 
            WHERE user_id = ? 
            ORDER BY id DESC LIMIT 5
        ''', (user_id,))
        records = cursor.fetchall()

    # Формуємо текст відповіді
    text = f"👤 **Мой кабинет**\n"
    text += f"📅 Текущий период: {period_name}\n"
    text += f"✅ **Отработано дней: {days_worked}**\n"

    await message.answer(text, parse_mode="Markdown")


@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    """Адмін-панель: статистика відпрацьованих днів по всім співробітникам."""

    # 1. Перевірка прав доступу
    if message.from_user.id not in ADMIN_IDS:
        return

    now = datetime.now()
    day = now.day

    # Визначаємо дати для фільтрації (Поточний період)
    if day <= 15:
        p_start = now.replace(day=1, hour=0, minute=0, second=0).strftime("%Y-%m-%d %H:%M:%S")
        period_text = f"01 - 15 {now.strftime('%m.%Y')}"
    else:
        p_start = now.replace(day=16, hour=0, minute=0, second=0).strftime("%Y-%m-%d %H:%M:%S")
        period_text = f"16 - конец {now.strftime('%m.%Y')}"

    # Початок місяця (для загальної статистики)
    m_start = now.replace(day=1, hour=0, minute=0, second=0).strftime("%Y-%m-%d %H:%M:%S")

    with sqlite3.connect('DataBase/office.db') as conn:
        cursor = conn.cursor()

        # Запит: Групуємо по користувачу і рахуємо унікальні дні
        # Використовуємо LEFT JOIN, щоб бачити навіть тих, хто ще не працював
        cursor.execute('''
            SELECT 
                e.full_name, 
                COUNT(DISTINCT CASE WHEN c.checkin_time >= ? THEN DATE(c.checkin_time) END) as period_days,
                COUNT(DISTINCT CASE WHEN c.checkin_time >= ? THEN DATE(c.checkin_time) END) as month_days
            FROM employees e
            LEFT JOIN checkins c ON e.user_id = c.user_id
            GROUP BY e.user_id
            ORDER BY period_days DESC
        ''', (p_start, m_start))

        results = cursor.fetchall()

    # Формуємо текст звіту
    text = f"👑 **Админ-панель: Статистика**\n"
    text += f"📅 Текущий период: `{period_text}`\n\n"
    text += "Сотрудник | Период | Месяц\n"
    text += "---------------------------\n"

    if results:
        for row in results:
            name = row[0]
            p_days = row[1]
            m_days = row[2]
            # Виділяємо активних працівників емодзі
            status_emoji = "⭐️" if p_days > 0 else "💤"
            text += f"{status_emoji} **{name}**: `{p_days}` дн. (всего: {m_days})\n"
    else:
        text += "❌ Сотрудники не найдены в базе."

    # Додаємо кнопку для вивантаження детального звіту (якщо потрібно в майбутньому)
    btn_refresh = InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_refresh")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[btn_refresh]])

    await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")


# Запуск
async def main():
    init_db()
    print("Бот запущен...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())