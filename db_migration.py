"""
Модуль для міграції та оновлення схеми бази даних
Додає підтримку геолокаційних даних
"""
import sqlite3
import os
from logger_config import get_logger

logger = get_logger(__name__)


def migrate_db(db_path='DataBase/office.db'):
    """
    Виконує міграції БД для новіших версій
    Безпечно додає нові колонки без втрати даних
    
    Args:
        db_path: Шлях до БД файлу
    """
    os.makedirs('DataBase', exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    logger.info("🔄 Початок міграції бази даних...")
    
    try:
        # --- Таблиця employees (основна) ---
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS employees (
                user_id INTEGER PRIMARY KEY,
                full_name TEXT NOT NULL,
                role TEXT DEFAULT 'worker',
                profession TEXT DEFAULT 'Не указано',
                salary REAL DEFAULT 0,
                language TEXT DEFAULT 'ru',
                created_at TEXT,
                updated_at TEXT
            )
        ''')
        logger.debug("✅ Таблиця employees OK")
        
        # --- Таблиця checkins (з геолокацією) ---
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS checkins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                full_name TEXT NOT NULL,
                checkin_time TEXT NOT NULL,
                checkin_latitude REAL,
                checkin_longitude REAL,
                checkout_time TEXT,
                checkout_latitude REAL,
                checkout_longitude REAL,
                site_name TEXT,
                distance_meters REAL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES employees(user_id)
            )
        ''')
        logger.debug("✅ Таблиця checkins OK")
        
        # --- Таблиця logs (для аудиту) ---
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT,
                description TEXT,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES employees(user_id)
            )
        ''')
        logger.debug("✅ Таблиця audit_logs OK")
        
        # --- МІГРАЦІЇ для старих БД (додаємо нові колонки, якщо їх немає) ---
        def add_column_if_not_exists(table, column_name, column_def):
            try:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column_name} {column_def}")
                logger.info(f"✨ Додана колонка: {table}.{column_name}")
            except sqlite3.OperationalError as e:
                if 'already exists' in str(e):
                    logger.debug(f"ℹ️  Колонка вже існує: {table}.{column_name}")
                else:
                    logger.warning(f"⚠️  Помилка при додаванні колонки: {e}")
        
        # Додаємо географічні колонки до старої таблиці checkins
        add_column_if_not_exists('checkins', 'checkin_latitude', 'REAL')
        add_column_if_not_exists('checkins', 'checkin_longitude', 'REAL')
        add_column_if_not_exists('checkins', 'checkout_latitude', 'REAL')
        add_column_if_not_exists('checkins', 'checkout_longitude', 'REAL')
        add_column_if_not_exists('checkins', 'distance_meters', 'REAL')
        add_column_if_not_exists('checkins', 'created_at', "TEXT DEFAULT CURRENT_TIMESTAMP")
        
        # Додаємо колонки в employees
        add_column_if_not_exists('employees', 'created_at', 'TEXT')
        add_column_if_not_exists('employees', 'updated_at', 'TEXT')
        
        conn.commit()
        logger.info("✅ Міграція БД завершена успішно")
        
    except Exception as e:
        logger.error(f"❌ Помилка під час міграції БД: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


def log_user_action(user_id, action, description, db_path='DataBase/office.db'):
    """
    Записує дію користувача в таблицю audit_logs для статистики
    
    Args:
        user_id: ID користувача
        action: Тип дії (checkin, checkout, edit_profile, etc)
        description: Деталізований опис (JSON можливо)
        db_path: Шлях до БД
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO audit_logs (user_id, action, description)
            VALUES (?, ?, ?)
        ''', (user_id, action, description))
        
        conn.commit()
        conn.close()
        
        logger.debug(f"📝 Аудит: user_id={user_id}, action={action}")
        
    except Exception as e:
        logger.error(f"❌ Помилка при записі в audit_logs: {e}")


if __name__ == "__main__":
    # Тест міграції
    from logger_config import setup_logging
    setup_logging()
    migrate_db()
    print("✅ Міграція завершена")
