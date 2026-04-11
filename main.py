import asyncio
import sqlite3
import os
from datetime import datetime
from dotenv import load_dotenv
import logging
from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart, Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from geopy.distance import geodesic
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram import types, F
from aiogram.exceptions import TelegramBadRequest



# Імпортуємо виправлені класи
from Registration import RegistrationNewUsers, Registration
class AdminBroadcast(StatesGroup):
    waiting_for_message = State()
class HREdit(StatesGroup):
    waiting_for_profession = State()
    waiting_for_salary = State()
class WorkerRequest(StatesGroup):
    waiting_for_message = State()

# Завантаження токена
load_dotenv("token.env")
TOKEN = os.getenv("TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Налаштування координат
CONSTRUCTION_SITES = {
    "Кальдера": (28.073849,-16.722580),
    "Нирвана": (28.092456, -16.723134),
    "Офис": (28.239064, -16.7975147)
}
MAX_DISTANCE = 150
ADMIN_IDS = [1366979749]

db_users = RegistrationNewUsers()


def init_db():
    if not os.path.exists('DataBase'):
        os.makedirs('DataBase')

    conn = sqlite3.connect('DataBase/office.db')
    cursor = conn.cursor()

    # Таблиця відміток
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS checkins(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            full_name TEXT,
            checkin_time TEXT,
            checkout_time TEXT,
            site_name TEXT
        )
    ''')

    # Таблиця співробітників (відразу з новими колонками для нових баз)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS employees(
            user_id INTEGER PRIMARY KEY,
            full_name TEXT,
            role TEXT,
            profession TEXT DEFAULT 'Не указано',
            salary REAL DEFAULT 0
        )
    ''')

    # --- ОНОВЛЕННЯ СТАРОЇ БАЗИ ДАНИХ ---
    # Якщо таблиця вже була створена раніше, додаємо колонки:
    try:
        cursor.execute("ALTER TABLE employees ADD COLUMN profession TEXT DEFAULT 'Не указано'")
    except sqlite3.OperationalError:
        pass  # Якщо колонка вже є - ігноруємо

    try:
        cursor.execute("ALTER TABLE employees ADD COLUMN salary REAL DEFAULT 0")
    except sqlite3.OperationalError:
        pass
        # -----------------------------------

    conn.commit()
    conn.close()
def get_all_users():
    """
        Збирати всі Telegram ID щоб розсилати підчас розсилки
        :return
    """
    conn = sqlite3.connect('DataBase/office.db')
    cursor = conn.cursor()
    # Беремо лише user_id з таблиці працівників
    cursor.execute("SELECT user_id FROM employees")
    users = cursor.fetchall()
    conn.close()
    return [user[0] for user in users] # Генератор списків
    # квадратні дужки означаються що в результаті виконання цієї операції я хочу отримати новий список

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

def get_main_keyboard(user_id: int):
    btn_location = KeyboardButton(text="📍 Отметиться на работе", request_location=True)
    btn_cabinet = KeyboardButton(text="👤 Мой кабинет")
    btn_request = KeyboardButton(text="💬 Написать админу") # НОВА КНОПКА

    # Макет клавіатури
    keyboard_layout = [
        [btn_location, btn_cabinet],
        [btn_request] # Додали в новий рядок
    ]

    if user_id in ADMIN_IDS:
        btn_admin = KeyboardButton(text="Админ-панель")
        keyboard_layout.append([btn_admin])

    return ReplyKeyboardMarkup(keyboard=keyboard_layout, resize_keyboard=True)
# --- Обробники ---
@dp.message(Command("admin"))
@dp.message(F.text == "Админ-панель")
async def admin_panel(message: types.Message):
    print(f"--- Нажата кнопка Админ-панель. ID юзера: {message.from_user.id} ---")

    # Перевірка прав
    if message.from_user.id not in ADMIN_IDS:
        print(f"❌ БЛОКУВАННЯ: ID {message.from_user.id} немає у списку ADMIN_IDS {ADMIN_IDS}")
        return

    print("✅ Права підтверджено. Генерую дашборд...")

    try:
        text, keyboard = get_admin_dashboard(is_refresh=False)
        print("✅ Дашборд згенеровано успішно. Відправляю в Telegram...")

        await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")
        print("✅ Повідомлення відправлено.")

        # Спроба видалити
        try:
            await message.delete()
            print("✅ Старе повідомлення видалено.")
        except Exception as e:
            print(f"⚠️ Не вдалося видалити повідомлення: {e}")

    except Exception as e:
        print(f"❌ КРИТИЧНА ПОМИЛКА при створенні адмінки: {e}")

@dp.message(CommandStart())
async def start_cmd(message: types.Message, state: FSMContext):
    """
        Обробка команди /start

        Перевіряє, чи зареєстрований користувач у базі даних
        - Якщо так: видає йому головне меню
        - Якщо ні: запускає процес реєстрації

        message (type.Message): Об'єкт повідомлення від користувача
        state (FSMContext): Машина станів для запам'ятовування кроків реєстрації
    """
    user_id = message.from_user.id
    if db_users.user_exists(user_id):
        # ТУТ ПЕРЕДАЄМО user_id
        await message.answer("Твой кабинет готов к работе", reply_markup=get_main_keyboard(user_id))
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

    # ТУТ ТАКОЖ ПЕРЕДАЄМО user_id
    await message.answer(f"✅ Регистрация успешна, {full_name}!", reply_markup=get_main_keyboard(user_id))
    await state.clear()

@dp.message(F.location)
async def handle_location(message: types.Message):
    user_id = message.from_user.id
    user_coords = (message.location.latitude, message.location.longitude)

    # Шукаємо, на якому об'єкті знаходиться людина
    current_site = None
    for site_name, site_coords in CONSTRUCTION_SITES.items():
        if geodesic(site_coords, user_coords).meters <= MAX_DISTANCE:
            current_site = site_name
            break

    if current_site:
        today_str = datetime.now().strftime("%Y-%m-%d")
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with sqlite3.connect('DataBase/office.db') as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT id FROM checkins WHERE user_id = ? AND checkin_time LIKE ?', (user_id, f"{today_str}%"))
            if cursor.fetchone():
                await message.answer(f"✅ Ты уже отметился сегодня! Объект: {current_site}")
            else:
                cursor.execute('SELECT full_name FROM employees WHERE user_id = ?', (user_id,))
                full_name = cursor.fetchone()[0]
                # Записуємо назву об'єкта в базу
                cursor.execute('INSERT INTO checkins (user_id, full_name, checkin_time, site_name) VALUES (?, ?, ?, ?)',
                               (user_id, full_name, current_time, current_site))
                conn.commit()
                await message.answer(f"🚀 Смена начата на объекте: {current_site}!\nВремя: {current_time}")
    else:
        await message.answer("❌ Ты слишком далеко от строительных объектов.")

async def morning_report():
    """Надсилає адміну звіт о 08:30 про тих, хто вже прийшов"""
    while True:
        now = datetime.now()
        if now.hour == 8 and now.minute == 30:
            today_str = now.strftime("%Y-%m-%d")

            with sqlite3.connect('DataBase/office.db') as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT site_name, full_name FROM checkins WHERE checkin_time LIKE ?', (f"{today_str}%",))
                records = cursor.fetchall()

            if records:
                # Групуємо дані: { "Кальдера": ["Степа", "Иван"], "Нирвана": ["Артем"] }
                report_data = {}
                for site, name in records:
                    if site not in report_data:
                        report_data[site] = []
                    report_data[site].append(name)

                msg = f"☀️ **Утренний отчет ({today_str})**\n\n"
                for site, workers in report_data.items():
                    msg += f"🏗 **{site}**: {', '.join(workers)}\n"
            else:
                msg = "На 08:30 еще никто не отметился."

            # Надсилаємо всім адмінам
            for admin_id in ADMIN_IDS:
                try:
                    await bot.send_message(admin_id, msg, parse_mode="Markdown")
                except:
                    pass

            await asyncio.sleep(61)
        await asyncio.sleep(30)

async def auto_checkout():
    """Фонова задача: кожен день о 16:00 автоматично закриває зміни"""
    while True:
        now = datetime.now()

        # Якщо зараз рівно 16:00
        if now.hour == 16 and now.minute == 0:
            today_str = now.strftime("%Y-%m-%d")
            checkout_str = now.strftime("%Y-%m-%d 16:00:00")

            with sqlite3.connect('DataBase/office.db') as conn:
                cursor = conn.cursor()
                # Знаходимо всі сьогоднішні записи, де ще немає часу виходу, і ставимо 16:00
                cursor.execute('''
                    UPDATE checkins 
                    SET checkout_time = ? 
                    WHERE checkin_time LIKE ? AND checkout_time IS NULL
                ''', (checkout_str, f"{today_str}%"))
                conn.commit()

            # Спимо 61 секунду, щоб уникнути повторного спрацювання в ту саму хвилину
            await asyncio.sleep(61)

            # Перевіряємо час кожні 30 секунд
        await asyncio.sleep(30)

@dp.message(F.text == "💬 Написать админу")
async def start_worker_request(message: types.Message, state: FSMContext):
    # Очищаємо чат від натискання кнопки
    try:
        await message.delete()
    except Exception:
        pass

    # Тимчасова клавіатура з кнопкою відміни
    cancel_kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="❌ Отмена")]], resize_keyboard=True)

    await state.set_state(WorkerRequest.waiting_for_message)
    await message.answer(
        "📝 **Напишите ваше сообщение руководителю:**\n\n",
        reply_markup=cancel_kb,
        parse_mode="Markdown"
    )

@dp.message(WorkerRequest.waiting_for_message)
async def process_worker_request(message: types.Message, state: FSMContext):
    user_id = message.from_user.id

    # Якщо передумав
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Действие отменено.", reply_markup=get_main_keyboard(user_id))
        return

    text = message.text

    # Дістаємо ім'я та поточний об'єкт працівника
    with sqlite3.connect('DataBase/office.db') as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT full_name FROM employees WHERE user_id = ?", (user_id,))
        user_data = cursor.fetchone()

        today_str = datetime.now().strftime("%Y-%m-%d")
        cursor.execute("SELECT site_name FROM checkins WHERE user_id = ? AND checkin_time LIKE ?", (user_id, f"{today_str}%"))
        site_data = cursor.fetchone()

    name = user_data[0] if user_data else "Неизвестный"
    site = site_data[0] if site_data else "Объект не определен (еще не отмечался)"

    # Формуємо повідомлення для тебе (адміна)
    admin_msg = f"⚠️ **ЗАПРОС ОТ РАБОТНИКА**\n\n"
    admin_msg += f"👷 **От кого:** `{name}`\n"
    admin_msg += f"📍 **Объект:** `{site}`\n\n"
    admin_msg += f"💬 **Текст:**\n{text}"

    # Відправляємо всім адмінам
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, admin_msg, parse_mode="Markdown")
        except:
            pass

    await state.clear()
    await message.answer("✅ Ваше сообщение успешно отправлено руководителю!", reply_markup=get_main_keyboard(user_id))

@dp.message(F.text == "👤 Мой кабинет")
async def my_cabinet(message: types.Message):
    # 1. Видаляємо повідомлення користувача ("👤 Мой кабинет"), щоб не засмічувати чат
    try:
        await message.delete()
    except Exception:
        pass

    user_id = message.from_user.id
    now = datetime.now()
    day = now.day

    # 2. Визначаємо звітний період
    if day <= 15:
        period_start = now.replace(day=1, hour=0, minute=0, second=0).strftime("%Y-%m-%d %H:%M:%S")
        period_name = f"с 01 по 15 {now.strftime('%m.%Y')}"
    else:
        period_start = now.replace(day=16, hour=0, minute=0, second=0).strftime("%Y-%m-%d %H:%M:%S")
        period_name = f"с 16 по конец {now.strftime('%m.%Y')}"

    with sqlite3.connect('DataBase/office.db') as conn:
        cursor = conn.cursor()

        # Отримуємо кількість відпрацьованих днів
        cursor.execute('''
            SELECT COUNT(DISTINCT DATE(checkin_time)) 
            FROM checkins 
            WHERE user_id = ? AND checkin_time >= ?
        ''', (user_id, period_start))
        days_worked = cursor.fetchone()[0]

        # Отримуємо посаду та ставку з HR-модуля
        cursor.execute('SELECT profession, salary FROM employees WHERE user_id = ?', (user_id,))
        user_data = cursor.fetchone()

        profession = user_data[0] if user_data and user_data[0] else "Не указано"
        salary = user_data[1] if user_data and user_data[1] else 0

    # 3. Рахуємо зароблені гроші
    earned = days_worked * salary

    # 4. Формуємо красивий текст
    text = f"👤 **Мой кабинет**\n\n"
    text += f"🛠 **Должность:** `{profession}`\n"
    text += f"💵 **Ставка (в день):** `{salary}`\n\n"
    text += f"📅 **Текущий период:** `{period_name}`\n"
    text += f"✅ **Отработано дней:** `{days_worked}`\n"
    text += f"➖➖➖➖➖➖➖➖\n"
    text += f"💰 **Заработано за период:** `{earned}`\n"

    # Відправляємо статистику (і заодно оновлюємо клавіатуру на всякий випадок)
    await message.answer(text, reply_markup=get_main_keyboard(user_id), parse_mode="Markdown")

def get_admin_dashboard(is_refresh=False):
    """Генерує текст статистики та клавіатуру для адмін-панелі."""
    now = datetime.now()
    day = now.day

    # Визначаємо дати для фільтрації
    if day <= 15:
        p_start = now.replace(day=1, hour=0, minute=0, second=0).strftime("%Y-%m-%d %H:%M:%S")
        period_text = f"01 - 15 {now.strftime('%m.%Y')}"
    else:
        p_start = now.replace(day=16, hour=0, minute=0, second=0).strftime("%Y-%m-%d %H:%M:%S")
        period_text = f"16 - конец {now.strftime('%m.%Y')}"

    m_start = now.replace(day=1, hour=0, minute=0, second=0).strftime("%Y-%m-%d %H:%M:%S")

    with sqlite3.connect('DataBase/office.db') as conn:
        cursor = conn.cursor()
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

    # Формуємо текст
    text = f" **Админ-панель: Статистика**\n"
    text += f"📅 Текущий период: `{period_text}`\n\n"
    text += "Сотрудник | Период | Месяц\n"
    text += "---------------------------\n"

    if results:
        for row in results:
            name = row[0]
            p_days = row[1]
            m_days = row[2]
            status_emoji = "" if p_days > 0 else "💤"
            text += f"{status_emoji} **{name}**: `{p_days}` дн. (всего: {m_days})\n"
    else:
        text += "❌ Сотрудники не найдены в базе.\n"

    # Якщо це оновлення, додаємо час
    if is_refresh:
        update_time = now.strftime("%H:%M:%S")
        text += f"\n🔄 *Обновлено:* `{update_time}`"

    # Збираємо всі 5 кнопок В ОДНОМУ МІСЦІ
    btn_refresh = InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_refresh")
    btn_broadcast = InlineKeyboardButton(text="✉️ Рассылка", callback_data="admin_broadcast")
    btn_active = InlineKeyboardButton(text="👷 Кто на объекте", callback_data="admin_active")
    btn_hr = InlineKeyboardButton(text="👥 Персонал (HR)", callback_data="admin_hr")
    btn_statistics = InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [btn_refresh],
        [btn_broadcast],
        [btn_active],
        [btn_statistics],
        [btn_hr]
    ])

    return text, keyboard


@dp.callback_query(F.data == "admin_refresh")
async def refresh_admin_panel(callback: types.CallbackQuery):
    """Оновлює існуючу адмін-панель."""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("У вас нет прав.", show_alert=True)
        return

    # Отримуємо текст і кнопки, але з міткою оновлення (True)
    text, keyboard = get_admin_dashboard(is_refresh=True)

    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
        await callback.answer("✅ Данные успешно обновлены!")
    except TelegramBadRequest:
        await callback.answer("Данные уже актуальны.", show_alert=False)

# Обработчик нажатия на inline-кнопку "Рассылка"
@dp.callback_query(F.data == "admin_broadcast")
async def start_broadcast(callback: types.CallbackQuery, state: FSMContext):
    # Проверка на админа на всякий случай
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("У вас нет прав для этого действия.", show_alert=True)
        return

    # Просим ввести текст
    await callback.message.answer(
        "📝 **Режим рассылки**\n\n"
        "Введите сообщение, которое получат все зарегистрированные сотрудники.\n"
        "Для отмены напишите слово `отмена`.",
        parse_mode="Markdown"
    )
    # Переводим бота в режим ожидания текста
    await state.set_state(AdminBroadcast.waiting_for_message)

    # Закрываем уведомление о нажатии кнопки
    await callback.answer()

# Обработчик самого текста рассылки
@dp.message(AdminBroadcast.waiting_for_message)
async def process_broadcast_message(message: types.Message, state: FSMContext):
    # Если передумали отправлять
    if message.text.lower() == 'отмена':
        await message.answer("❌ Рассылка отменена.")
        await state.clear()
        return

    # Получаем список всех сотрудников из базы
    with sqlite3.connect('DataBase/office.db') as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM employees")
        users = cursor.fetchall()

    success_count = 0
    block_count = 0

    await message.answer("⏳ Начинаю рассылку... Это может занять несколько секунд.")

    # Рассылаем всем по очереди
    for user_row in users:
        user_id = user_row[0]
        try:
            # Отправляем сообщение
            await message.bot.send_message(
                chat_id=user_id,
                text=f"⚠️ **ОБЪЯВЛЕНИЕ:**\n\n{message.text}",
                parse_mode="Markdown"
            )
            success_count += 1
            # Микро-пауза для защиты от блокировки Telegram (антиспам)
            await asyncio.sleep(0.05)
        except Exception as e:
            # Если сотрудник заблокировал бота или удалил чат
            block_count += 1
            logging.error(f"Не удалось отправить {user_id}: {e}")

    # Сбрасываем состояние
    await state.clear()

    # Выводим отчет
    await message.answer(
        f"✅ **Рассылка завершена!**\n\n"
        f"Успешно доставлено: `{success_count}` чел.\n"
        f"Недоставлено (заблокировали бота): `{block_count}` чел.",
        parse_mode="Markdown"
    )

@dp.callback_query(F.data == "admin_stats")
async def advanced_statistics(callback: types.CallbackQuery):
    """Розширена статистика: фінанси та об'єкти за поточний місяць."""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("У вас нет прав.", show_alert=True)
        return

    now = datetime.now()
    # Беремо поточний рік та місяць у форматі YYYY-MM (наприклад, 2023-10)
    current_month_str = now.strftime("%Y-%m")
    display_month = now.strftime("%m.%Y")

    with sqlite3.connect('DataBase/office.db') as conn:
        cursor = conn.cursor()

        # --- 1. ФІНАНСОВА СТАТИСТИКА (Зарплатний фонд) ---
        # Рахуємо дні і множимо на ставку (вважаємо, що salary - це ставка за 1 день/зміну)
        cursor.execute('''
            SELECT 
                e.full_name, 
                e.profession,
                e.salary, 
                COUNT(DISTINCT DATE(c.checkin_time)) as worked_days
            FROM employees e
            JOIN checkins c ON e.user_id = c.user_id
            WHERE c.checkin_time LIKE ?
            GROUP BY e.user_id
            ORDER BY worked_days DESC
        ''', (f"{current_month_str}%",))

        finance_records = cursor.fetchall()

        # --- 2. СТАТИСТИКА ПО ОБ'ЄКТАХ ---
        # Рахуємо, скільки всього виходів на роботу було на кожному об'єкті
        cursor.execute('''
            SELECT 
                site_name, 
                COUNT(id) as total_shifts
            FROM checkins 
            WHERE checkin_time LIKE ? AND site_name IS NOT NULL
            GROUP BY site_name
            ORDER BY total_shifts DESC
        ''', (f"{current_month_str}%",))

        site_records = cursor.fetchall()

    # --- ФОРМУЄМО ТЕКСТ ЗВІТУ ---
    text = f"📊 **Глубокая аналитика за {display_month}**\n\n"

    # Блок 1: Фінанси
    text += "💰 **Фонд оплаты труда (предварительно):**\n"
    total_budget = 0

    if finance_records:
        for name, prof, salary, days in finance_records:
            # Рахуємо зароблене (ставка * дні)
            earned = salary * days
            total_budget += earned

            # Робимо гарне форматування, наприклад: Иван (Сварщик): 5 дн * 2000 = 10000
            prof_text = f" ({prof})" if prof != 'Не указано' else ""
            text += f"▫️ **{name}**{prof_text}: `{days}` дн. ✖️ {salary} = **{earned}**\n"

        text += f"➖➖➖➖➖➖➖➖\n"
        text += f"💵 **ОБЩИЙ ИТОГ К ВЫПЛАТЕ:** `{total_budget}`\n\n"
    else:
        text += "▫️ Нет данных за этот месяц.\n\n"

    # Блок 2: Об'єкти
    text += "🏗 **Загруженность объектов (человеко-смены):**\n"
    if site_records:
        for site, shifts in site_records:
            text += f"📍 **{site}**: `{shifts}` смен\n"
    else:
        text += "▫️ Нет активности на объектах.\n"

    # Додаємо кнопку повернення в головну адмінку
    btn_back = InlineKeyboardButton(text="🔙 Назад в Админ-панель",
                                    callback_data="admin_refresh")  # Можемо використати існуючий колбек
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[btn_back]])

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")


@dp.callback_query(F.data == "admin_active")
async def show_active_workers(callback: types.CallbackQuery):
    today_str = datetime.now().strftime("%Y-%m-%d")
    with sqlite3.connect('DataBase/office.db') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT site_name, full_name, checkout_time FROM checkins WHERE checkin_time LIKE ?', (f"{today_str}%",))
        records = cursor.fetchall()

    if not records:
        await callback.message.answer("🤷‍♂️ На объектах пусто.")
    else:
        # Логіка групування аналогічна ранковому звіту
        active_by_site = {}
        for site, name, is_out in records:
            if site not in active_by_site:
                active_by_site[site] = []
            status = "🟢" if is_out is None else "🔴"
            active_by_site[site].append(f"{status} {name}")

        text = f"👷 **Текущая ситуация ({today_str}):**\n\n"
        for site, staff in active_by_site.items():
            text += f"📍 **{site}**:\n" + "\n".join(staff) + "\n\n"

        await callback.message.answer(text, parse_mode="Markdown")
    await callback.answer()

# --- HR МОДУЛЬ ---

@dp.callback_query(F.data == "admin_hr")
async def hr_menu(callback: types.CallbackQuery):
    """Виводить список усіх працівників у вигляді кнопок."""
    if callback.from_user.id not in ADMIN_IDS:
        return

    with sqlite3.connect('DataBase/office.db') as conn:
        cursor = conn.cursor()
        # Витягуємо ID та імена всіх зареєстрованих працівників
        cursor.execute("SELECT user_id, full_name FROM employees")
        users = cursor.fetchall()

    if not users:
        await callback.answer("Сотрудники не найдены.", show_alert=True)
        return

    # Створюємо клавіатуру, де кожна кнопка — це працівник
    # У callback_data ми "зашиваємо" його ID (наприклад, hr_user_123456)
    inline_kb = []
    for user_id, name in users:
        inline_kb.append([InlineKeyboardButton(text=f"👷 {name}", callback_data=f"hr_user_{user_id}")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=inline_kb)

    await callback.message.edit_text(
        "👥 **Управление персоналом**\n\nВыберите сотрудника для просмотра и редактирования данных:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )


@dp.callback_query(F.data.startswith("hr_user_"))
async def hr_employee_card(callback: types.CallbackQuery):
    """Відкриває картку конкретного працівника."""
    if callback.from_user.id not in ADMIN_IDS:
        return

    # Витягуємо ID працівника з назви кнопки
    target_user_id = int(callback.data.split("_")[2])

    with sqlite3.connect('DataBase/office.db') as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT full_name, profession, salary FROM employees WHERE user_id = ?", (target_user_id,))
        user_data = cursor.fetchone()

    if not user_data:
        await callback.answer("Ошибка: пользователь не найден.", show_alert=True)
        return

    full_name, profession, salary = user_data

    # Формуємо текст картки
    text = f"🪪 **Карточка сотрудника**\n\n"
    text += f"👤 **Имя:** `{full_name}`\n"
    text += f"🛠 **Профессия:** `{profession}`\n"
    text += f"💰 **Ставка (ЗП):** `{salary}`\n"

    # Кнопки для зміни даних (передаємо ID працівника в callback_data)
    btn_prof = InlineKeyboardButton(text="✏️ Изменить профессию", callback_data=f"hr_edit_prof_{target_user_id}")
    btn_sal = InlineKeyboardButton(text="💵 Изменить зарплату", callback_data=f"hr_edit_sal_{target_user_id}")
    btn_back = InlineKeyboardButton(text="🔙 Назад к списку", callback_data="admin_hr")

    keyboard = InlineKeyboardMarkup(inline_keyboard=[[btn_prof], [btn_sal], [btn_back]])

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")


# --- Зміна професії ---
@dp.callback_query(F.data.startswith("hr_edit_prof_"))
async def start_edit_profession(callback: types.CallbackQuery, state: FSMContext):
    target_user_id = int(callback.data.split("_")[3])

    # Зберігаємо ID працівника в пам'ять стану
    await state.update_data(target_user_id=target_user_id)
    await state.set_state(HREdit.waiting_for_profession)

    await callback.message.answer("📝 Введите новую **профессию** для этого сотрудника (например: Бетонщик, Сварщик):",
                                  parse_mode="Markdown")
    await callback.answer()


@dp.message(HREdit.waiting_for_profession)
async def process_new_profession(message: types.Message, state: FSMContext):
    new_profession = message.text
    # Дістаємо збережений ID працівника
    data = await state.get_data()
    target_user_id = data.get("target_user_id")

    with sqlite3.connect('DataBase/office.db') as conn:
        cursor = conn.cursor()
        # Оновлюємо базу
        cursor.execute("UPDATE employees SET profession = ? WHERE user_id = ?", (new_profession, target_user_id))
        conn.commit()

        # ОДРАЗУ дістаємо актуальні дані для картки
        cursor.execute("SELECT full_name, profession, salary FROM employees WHERE user_id = ?", (target_user_id,))
        user_data = cursor.fetchone()

    full_name, profession, salary = user_data

    # Формуємо текст з підтвердженням і самою карткою
    text = f"✅ **Профессия успешно изменена!**\n\n"
    text += f"🪪 **Карточка сотрудника**\n"
    text += f"👤 **Имя:** `{full_name}`\n"
    text += f"🛠 **Профессия:** `{profession}`\n"
    text += f"💰 **Ставка (ЗП):** `{salary}`\n"

    # Повертаємо кнопки керування
    btn_prof = InlineKeyboardButton(text="✏️ Изменить профессию", callback_data=f"hr_edit_prof_{target_user_id}")
    btn_sal = InlineKeyboardButton(text="💵 Изменить зарплату", callback_data=f"hr_edit_sal_{target_user_id}")
    btn_back = InlineKeyboardButton(text="🔙 Назад к списку", callback_data="admin_hr")

    keyboard = InlineKeyboardMarkup(inline_keyboard=[[btn_prof], [btn_sal], [btn_back]])

    await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")
    await state.clear()

# --- Зміна зарплати ---
@dp.callback_query(F.data.startswith("hr_edit_sal_"))
async def start_edit_salary(callback: types.CallbackQuery, state: FSMContext):
    target_user_id = int(callback.data.split("_")[3])

    await state.update_data(target_user_id=target_user_id)
    await state.set_state(HREdit.waiting_for_salary)

    await callback.message.answer("💵 Введите новую **ставку (зарплату)** цифрами (например: 2500):", parse_mode="Markdown")
    await callback.answer()


@dp.message(HREdit.waiting_for_salary)
async def process_new_salary(message: types.Message, state: FSMContext):
    # Перевіряємо, чи ввів адмін саме цифри
    if not message.text.replace('.', '', 1).isdigit():
        await message.answer("❌ Пожалуйста, введите только число.")
        return

    new_salary = float(message.text)
    data = await state.get_data()
    target_user_id = data.get("target_user_id")

    with sqlite3.connect('DataBase/office.db') as conn:
        cursor = conn.cursor()
        # Оновлюємо базу
        cursor.execute("UPDATE employees SET salary = ? WHERE user_id = ?", (new_salary, target_user_id))
        conn.commit()

        # ОДРАЗУ дістаємо актуальні дані для картки
        cursor.execute("SELECT full_name, profession, salary FROM employees WHERE user_id = ?", (target_user_id,))
        user_data = cursor.fetchone()

    full_name, profession, salary = user_data

    # Формуємо текст з підтвердженням і самою карткою
    text = f"✅ **Ставка успешно изменена!**\n\n"
    text += f"🪪 **Карточка сотрудника**\n"
    text += f"👤 **Имя:** `{full_name}`\n"
    text += f"🛠 **Профессия:** `{profession}`\n"
    text += f"💰 **Ставка (ЗП):** `{salary}`\n"

    # Повертаємо кнопки керування
    btn_prof = InlineKeyboardButton(text="✏️ Изменить профессию", callback_data=f"hr_edit_prof_{target_user_id}")
    btn_sal = InlineKeyboardButton(text="💵 Изменить зарплату", callback_data=f"hr_edit_sal_{target_user_id}")
    btn_back = InlineKeyboardButton(text="🔙 Назад к списку", callback_data="admin_hr")

    keyboard = InlineKeyboardMarkup(inline_keyboard=[[btn_prof], [btn_sal], [btn_back]])

    await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")
    await state.clear()

# Запуск
async def main():
    init_db()
    print("Бот запущен...")
    asyncio.create_task(morning_report())
    asyncio.create_task(auto_checkout())

    await dp.start_polling(bot)



if __name__ == "__main__":
    asyncio.run(main())