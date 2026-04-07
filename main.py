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

# Завантаження токена
load_dotenv("token.env")
TOKEN = os.getenv("TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Налаштування координат
CONSTRUCTION_SITES = {
    "Кальдера": (28.073849,-16.722580),
    "Нирвана": (28.092456, -16.723134),
    "Офис": (37.389092, -5.984458)
}
MAX_DISTANCE = 150
ADMIN_IDS = [1366979749]

db_users = RegistrationNewUsers()


def init_db():
    """
        Ініціалізація бази даних при старті бота.
        1. Перевірка наявносі директорії DataBase. Якщо її немає - створює.
        2. Підключається до файлу 'office.db' (або створює)
        3. Створює таблицю 'checkins' для фіксації робочого часу(id, користувач, час початку, час завершення)
        4. Створює таблицю ''employees' для збереження списку працівників.
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
            checkout_time TEXT,
            site_name TEXT
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
    # Базові кнопки для всіх
    btn_location = KeyboardButton(text="📍 Отметиться на работе", request_location=True)
    btn_cabinet = KeyboardButton(text="👤 Мой кабинет")

    # Базовий макет (два ряди)
    keyboard_layout = [
        [btn_location,btn_cabinet]
    ]

    # Якщо ID користувача є в списку адмінів, додаємо йому ще одну кнопку знизу
    if user_id in ADMIN_IDS:
        btn_admin = KeyboardButton(text="👑 Админ-панель")
        keyboard_layout.append([btn_admin])

    return ReplyKeyboardMarkup(keyboard=keyboard_layout, resize_keyboard=True)

# --- Обробники ---

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
@dp.message(F.text == "👑 Админ-панель")
async def admin_panel(message: types.Message):
    """Адмін-панель: статистика відпрацьованих днів по всім співробітникам."""

    # 1. Перевірка прав доступу
    if message.from_user.id not in ADMIN_IDS:
        return

    # ... далі весь код без змін ...

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
        # ... (твой предыдущий код админ-панели до кнопок) ...

        # Создаем кнопки: Обновить и Рассылка
    btn_refresh = InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_refresh")
    btn_broadcast = InlineKeyboardButton(text="✉️ Рассылка", callback_data="admin_broadcast")
    btn_active = InlineKeyboardButton(text="👷 Кто на объекте", callback_data="admin_active")

        # Размещаем кнопки одна под другой (каждая в своем списке)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[btn_refresh], [btn_broadcast],[btn_active]])

    await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")

@dp.callback_query(F.data == "admin_refresh")
async def refresh_admin_panel(callback: types.CallbackQuery):
    # 1. Захист від сторонніх
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("У вас нет прав.", show_alert=True)
        return

    now = datetime.now()
    day = now.day

    # Визначаємо дати для фільтрації (копіюємо логіку з admin_panel)
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

    # 2. Формуємо новий текст
    text = f"👑 **Админ-панель: Статистика**\n"
    text += f"📅 Текущий период: `{period_text}`\n\n"
    text += "Сотрудник | Период | Месяц\n"
    text += "---------------------------\n"

    if results:
        for row in results:
            name = row[0]
            p_days = row[1]
            m_days = row[2]
            status_emoji = "⭐️" if p_days > 0 else "💤"
            text += f"{status_emoji} **{name}**: `{p_days}` дн. (всего: {m_days})\n"
    else:
        text += "❌ Сотрудники не найдены в базе.\n"

    # ДОДАЄМО ТОЧНИЙ ЧАС, щоб уникнути помилки Telegram
    update_time = now.strftime("%H:%M:%S")
    text += f"\n🔄 *Обновлено:* `{update_time}`"

    # 3. Заново створюємо клавіатуру, щоб вона не зникла
    btn_refresh = InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_refresh")
    btn_broadcast = InlineKeyboardButton(text="✉️ Рассылка", callback_data="admin_broadcast")
    btn_active = InlineKeyboardButton(text="👷 Кто на объекте", callback_data="admin_active")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[btn_refresh], [btn_broadcast], [btn_active]])

    # 4. Пробуємо оновити повідомлення
    try:
        # edit_text замінює старий текст повідомлення на новий
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
        # Закриваємо годинник на кнопці та показуємо спливаюче вікно
        await callback.answer("✅ Данные успешно обновлены!")
    except TelegramBadRequest:
        # Якщо текст взагалі не змінився (навіть секунди збіглися)
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

# Запуск
async def main():
    init_db()
    print("Бот запущен...")
    asyncio.create_task(morning_report())
    asyncio.create_task(auto_checkout())

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())