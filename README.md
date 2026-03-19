# ⏱ Office Check-in Telegram Bot

Telegram бот для контролю **робочого часу співробітників** з перевіркою **GPS-локації**.

Бот дозволяє співробітникам:

* реєструватися
* відмічати **початок робочого дня**
* відмічати **завершення зміни**
* переглядати свою історію відміток

Адміністратор може:

* переглядати **звіт за сьогодні**
* **підтверджувати нових співробітників**

---

# 🚀 Features

* 📍 Check-in через GPS
* 🔴 Check-out із роботи
* 👤 Особистий кабінет співробітника
* 👑 Адмін-панель
* 🗄 SQLite база даних
* ⚡ Асинхронна архітектура (aiogram)

---

# 🛠 Technologies

* Python 3.10+
* aiogram 3
* SQLite
* geopy
* python-dotenv
* asyncio

---

# 📂 Project Structure

```
project/
│
├── bot.py
├── Registration.py
├── token.env
│
├── DataBase/
│   └── office.db
│
└── requirements.txt
```

---

# ⚙ Installation

## 1. Clone repository

```
git clone https://github.com/yourusername/office-checkin-bot.git
cd office-checkin-bot
```

---

## 2. Install dependencies

```
pip install -r requirements.txt
```

---

## 3. Create .env file

```
token.env
```

```
TOKEN=YOUR_TELEGRAM_BOT_TOKEN
```

---

# ▶ Run Bot

```
python bot.py
```

---

# 🗄 Database

Бот використовує **SQLite**.

База створюється автоматично:

```
DataBase/office.db
```

## employees

| field     | type    | description |
| --------- | ------- | ----------- |
| user_id   | INTEGER | Telegram ID |
| full_name | TEXT    | Name        |
| role      | TEXT    | Role        |

### roles

```
worker
admin
pending
```

---

## checkins

| field         | type    |
| ------------- | ------- |
| id            | INTEGER |
| user_id       | INTEGER |
| full_name     | TEXT    |
| checkin_time  | TEXT    |
| checkout_time | TEXT    |

---

# 📍 Location Check

Бот перевіряє дистанцію до офісу.

```
MAX_DISTANCE = 100
```

Максимальна відстань:

**100 метрів**

---

# 👤 User Commands

## /start

Реєстрація або відкриття меню.

---

## 📍 Отметиться на работе

Початок зміни.

---

## 🔴 Уйти с работы

Завершення зміни.

---

## 👤 Мой кабинет

Показує **5 останніх відміток**.

---

# 👑 Admin Commands

## /admin

Показує звіт за сьогодні.

---

## /approve USER_ID

Підтвердити користувача.

Example:

```
/approve 123456789
```

---

# 🔒 Security

* перевірка ролей
* перевірка координат
* перевірка адміністратора
* захист від подвійного check-in

---

# 📊 Planned Features

* Excel reports
* Weekly reports
* Monthly reports
* Admin dashboard
* Working hours calculation

---

# 👨‍💻 Author

Telegram Work Time Tracking Bot
