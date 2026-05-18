# 🚀 QUICK START - Нові можливості

## 1️⃣ Запуск бота з логуванням

```bash
python main.py
```

**Логи автоматично записуються у**: `DataBase/logs/bot.log`

---

## 2️⃣ Просмотр логов

### Живой просмотр (як в реальному часі):
```bash
tail -f DataBase/logs/bot.log
```

### Пошук помилок:
```bash
grep "ERROR" DataBase/logs/bot.log
```

### Пошук геолокационних подій:
```bash
grep "geo\|📍" DataBase/logs/bot.log
```

### Пошук адмін-операцій:
```bash
grep "admin\|🔐" DataBase/logs/bot.log
```

---

## 3️⃣ Структура логів

Кожна рядок має формат:
```
2026-05-18 10:30:45 [DEBUG   ] BotLogger.geo.handle_location:315 - 📍 Геолокація отримана від користувача 123456789: (28.073849, -16.7225)
```

| Частина | Значення |
|---------|----------|
| `2026-05-18 10:30:45` | Дата та час |
| `DEBUG` | Рівень логування |
| `BotLogger.geo` | Компонент (geo, db, admin) |
| `handle_location:315` | Функція та номер рядка |
| Текст | Саме повідомлення |

---

## 4️⃣ GPS-дані в БД

Тепер таблиця `checkins` зберігає точні координати:

```sql
-- Приклад запиту
SELECT 
  full_name,
  checkin_time,
  checkin_latitude,
  checkin_longitude,
  site_name,
  distance_meters
FROM checkins
WHERE DATE(checkin_time) = '2026-05-18'
ORDER BY checkin_time DESC;
```

**Результат:**
```
full_name   | checkin_time        | lat      | lon       | site_name | distance
------------|---------------------|----------|-----------|-----------|----------
Іван        | 2026-05-18 08:45:30 | 28.0738  | -16.7226  | Кальдера  | 15.2
Петро       | 2026-05-18 08:52:15 | 28.0724  | -16.7220  | Кальдера  | 152.8
Степа       | 2026-05-18 09:00:00 | 28.0728  | -16.7222  | Нирвана   | 8.5
```

---

## 5️⃣ Аналіз даних

### Python скрипт для аналізу геолокації:

```python
import sqlite3
from datetime import datetime, timedelta

conn = sqlite3.connect('DataBase/office.db')
cursor = conn.cursor()

# Сьогодні
today = datetime.now().strftime("%Y-%m-%d")

# Отримати всі відмітки за сьогодні
cursor.execute('''
    SELECT 
        full_name,
        checkin_time,
        site_name,
        distance_meters
    FROM checkins
    WHERE DATE(checkin_time) = ?
    ORDER BY checkin_time
''', (today,))

print(f"\n📊 ЗВІТ ПО ГЕОЛОКАЦІЇ ({today})\n")
print(f"{'Імя':<15} | {'Час':<19} | {'Об`єкт':<10} | {'Дистанція':<10}")
print("-" * 60)

for name, time, site, distance in cursor.fetchall():
    status = "✅" if distance < 50 else "⚠️ " if distance < 150 else "❌"
    print(f"{name:<15} | {time:<19} | {site:<10} | {status} {distance:>6.1f}м")

conn.close()
```

**Вихід:**
```
📊 ЗВІТ ПО ГЕОЛОКАЦІЇ (2026-05-18)

Імя            | Час                 | Об`єкт     | Дистанція
------------------------------------------------------------
Іван           | 2026-05-18 08:45:30 | Кальдера   | ✅  15.2м
Петро          | 2026-05-18 08:52:15 | Кальдера   | ⚠️  152.8м
Степа          | 2026-05-18 09:00:00 | Нирвана    | ✅   8.5м
```

---

## 6️⃣ Audit-логи (Нова таблиця)

Для отслідження всіх дій:

```sql
SELECT user_id, action, description, timestamp
FROM audit_logs
ORDER BY timestamp DESC
LIMIT 10;
```

**Типи дій:**
- `checkin` - користувач відмітився
- `broadcast` - адмін надіслав розсилку
- `hr_edit` - адмін змінив дані HR
- `checkout` - автоматичне закриття зміни

---

## 7️⃣ Опціональні улучшення

### Експорт логів у файл:
```bash
# Експортувати всі помилки
grep "ERROR" DataBase/logs/bot.log > errors_report.txt

# Експортувати за період часу
grep "2026-05-18 09:" DataBase/logs/bot.log > morning_report.txt
```

### Ежедневний бекап БД:
```bash
# Створити бекап
cp DataBase/office.db DataBase/office.db.$(date +%Y%m%d).backup

# Або додати в cron (Linux/Mac):
# 0 2 * * * cd /home/yevhen/Стільниця/BotWork && cp DataBase/office.db DataBase/office.db.$(date +\%Y\%m\%d).backup
```

---

## 8️⃣ Рівні логування

| Рівень | Символ | Використання |
|--------|--------|-------------|
| DEBUG | 🔍 | Детальна інформація про роботу |
| INFO | ✅ | Важливі подійі (успіхи) |
| WARNING | ⚠️ | Попередження (але не критично) |
| ERROR | ❌ | Помилки, але не критичні |
| CRITICAL | 🔴 | Критичні помилки, потрібна дія |

Поточне налаштування: **DEBUG** (повна інформація)

---

## 9️⃣ Заключ

✅ **Готово до production**

Всі покращення спроектовані так, щоб не порушити існуючий функціонал:
- GPS-дані записуються автоматично
- Логи пишуться в фон, не уповільнюючи бот
- Старі дані в БД залишаються в цілості

**Питання?** Дивіться `IMPROVEMENTS.md` для подробного звіту
