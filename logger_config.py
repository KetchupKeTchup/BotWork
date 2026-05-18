"""
Модуль конфігурації логування для Telegram-бота
"""
import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler

# Створюємо папку для логів, якщо її нема
LOG_DIR = 'DataBase/logs'
os.makedirs(LOG_DIR, exist_ok=True)


def setup_logging(log_level=logging.DEBUG):
    """
    Налаштовує систему логування для всього додатку
    
    Args:
        log_level: Рівень логування (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    
    Returns:
        logger: Налаштований логер
    """
    
    logger = logging.getLogger('BotLogger')
    logger.setLevel(log_level)
    
    # Формат логів
    formatter = logging.Formatter(
        fmt='%(asctime)s [%(levelname)-8s] %(name)s.%(funcName)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # --- Файловий обробник (Rotating File Handler) ---
    # Максимальний розмір файлу: 5MB, зберігаємо останні 5 файлів
    log_file = os.path.join(LOG_DIR, 'bot.log')
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,  # 5MB
        backupCount=5
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # --- Консольний обробник ---
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger


def get_logger(name):
    """
    Отримати логер для конкретного модуля
    
    Args:
        name: Назва модуля (__name__)
    
    Returns:
        logger: Логер для цього модуля
    """
    return logging.getLogger(name)


# Спеціалізовані логери для різних компонентів
def create_component_logger(component_name):
    """
    Створити окремий логер для компоненту (наприклад, "geo", "db", "admin")
    
    Args:
        component_name: Назва компоненту
    
    Returns:
        logger: Логер для компоненту
    """
    logger = logging.getLogger(f'BotLogger.{component_name}')
    return logger
