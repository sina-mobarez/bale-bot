# 🤖 Bale Registration Bot

A production-ready **Django + python-telegram-bot** application that:

- Asks users a **configurable set of questions** via a Bale messenger bot
- **Validates** answers (phone, email, number, multiple-choice)
- **Stores** all registrations in PostgreSQL
- Sends a **customizable final message** (text / file / photo / link) on completion
- Provides a **rich Django Admin panel** (Jazzmin UI) for managing questions, final messages, and viewing registrations
- Exports registrations to **CSV**

---

## Table of Contents

1. [Architecture](#architecture)
2. [Quick Start (Docker)](#quick-start-docker)
3. [Quick Start (Local)](#quick-start-local)
4. [Admin Panel Guide](#admin-panel-guide)
5. [Bot Commands](#bot-commands)
6. [Environment Variables](#environment-variables)
7. [Management Commands](#management-commands)
8. [Project Structure](#project-structure)
9. [Production Deployment](#production-deployment)
10. [Extending the Bot](#extending-the-bot)

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Docker Compose                        │
│                                                         │
│  ┌──────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │ PostgreSQL│←───│  Django Web  │    │  Bale Bot    │  │
│  │  (db)    │    │  (Gunicorn)  │    │  (polling)   │  │
│  └──────────┘    │  port 8000   │    │              │  │
│        ↑         └──────────────┘    └──────────────┘  │
│        │                ↑                    ↑          │
│        └────────────────┴────────────────────┘          │
│                   shared DB + media                     │
└─────────────────────────────────────────────────────────┘
         ↑
    ┌──────────┐
    │  Nginx   │  (optional, for HTTPS in production)
    │  80/443  │
    └──────────┘
```

**Key tech choices:**
- **`python-telegram-bot` v21** (async) pointed at Bale's API endpoint `https://tapi.bale.ai/bot`
- **Django 4.2** with async ORM — the bot uses `sync_to_async` wrappers, zero blocking
- **Jazzmin** for a polished, RTL-friendly admin UI
- **ConversationHandler** with dynamic question loading from DB per update

---

## Quick Start (Docker)

### Prerequisites
- Docker ≥ 24 and Docker Compose v2
- A Bale bot token from **@BotFather** in Bale messenger

### Steps

```bash
# 1. Clone / unzip the project
cd bale_registration_bot

# 2. Configure environment
cp .env.example .env
nano .env  # fill in BALE_BOT_TOKEN, DB_PASSWORD, SECRET_KEY, etc.

# 3. Build and start
docker compose up -d --build

# 4. Seed sample questions (optional)
docker compose exec bot python manage.py seed_sample_data

# 5. Open the admin panel
open http://localhost:8000/admin/
# Login: DJANGO_SUPERUSER_USERNAME / DJANGO_SUPERUSER_PASSWORD from .env
```

That's it. The bot is polling Bale and the admin is live.

---

## Quick Start (Local)

```bash
# 1. Create a virtual environment
python -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env — set DB credentials and BALE_BOT_TOKEN
# For local dev you can use SQLite by changing DATABASES in settings.py

# 4. Apply migrations
python manage.py migrate

# 5. Create superuser
python manage.py createsuperuser

# 6. Seed sample data
python manage.py seed_sample_data

# 7. Terminal A — Django admin
python manage.py runserver

# 8. Terminal B — Bale bot
python manage.py runbot
```

---

## Admin Panel Guide

Open `http://localhost:8000/admin/` and log in.

### Creating Questions (`سوالات`)

| Field | Description |
|---|---|
| **ترتیب (Order)** | Questions are asked in ascending order (1, 2, 3…) |
| **متن سوال (Text)** | The message sent to the user |
| **نام فیلد (Field Name)** | Slug key used to store the answer in JSON (e.g. `full_name`) |
| **نوع سوال (Type)** | `text` / `phone` / `email` / `number` / `choice` |
| **گزینه‌ها (Choices)** | For `choice` type: one option per line |
| **راهنمای اعتبارسنجی** | Error message shown on invalid input |
| **اجباری (Required)** | If checked, blank answers are rejected |
| **فعال (Active)** | Toggle to include/exclude without deleting |

### Creating a Final Message (`پیام‌های نهایی`)

Choose one of six types:

| Type | What gets sent |
|---|---|
| `متن` | A plain Markdown text message |
| `فایل` | A document/file attachment |
| `تصویر` | A photo |
| `لینک` | Text + inline button linking to a URL |
| `متن + فایل` | Text message followed by a file |
| `متن + لینک` | Text message + inline link button |

> ⚠️ Only **one** FinalMessage can be active. Activating a new one auto-deactivates the previous one.

### Viewing Registrations

- **کاربران ربات** — all users who have started the bot
- **جلسات ثبت‌نام** — each session shows a formatted table of Q→A pairs
- Click any user to see their inline session with all answers

---

## Bot Commands

| Command | Description |
|---|---|
| `/start` | Begin registration (or resume if in progress) |
| `/cancel` | Cancel the current registration flow |
| `/restart` | Reset session and start fresh from Q1 |

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `SECRET_KEY` | ✅ | — | Django secret key |
| `DEBUG` | | `False` | Enable debug mode |
| `ALLOWED_HOSTS` | ✅ | `localhost` | Comma-separated host list |
| `BALE_BOT_TOKEN` | ✅ | — | Token from @BotFather in Bale |
| `BALE_API_BASE_URL` | | `https://tapi.bale.ai/bot` | Bale API base URL |
| `BALE_FILE_BASE_URL` | | `https://tapi.bale.ai/file/bot` | Bale file API URL |
| `DB_NAME` | ✅ | `bale_bot_db` | PostgreSQL database name |
| `DB_USER` | ✅ | `bale_bot_user` | PostgreSQL user |
| `DB_PASSWORD` | ✅ | — | PostgreSQL password |
| `DB_HOST` | | `db` | DB host (use `localhost` for local dev) |
| `DB_PORT` | | `5432` | DB port |
| `DJANGO_SUPERUSER_USERNAME` | | `admin` | Auto-created admin username |
| `DJANGO_SUPERUSER_PASSWORD` | | — | Auto-created admin password |
| `DJANGO_SUPERUSER_EMAIL` | | — | Auto-created admin email |

---

## Management Commands

```bash
# Start the bot process
python manage.py runbot

# Seed sample questions + final message for testing
python manage.py seed_sample_data

# Re-seed (deletes existing data first)
python manage.py seed_sample_data --reset

# Export all completed registrations to CSV
python manage.py export_registrations

# Export to a specific path
python manage.py export_registrations --output /tmp/users.csv

# Standard Django commands
python manage.py migrate
python manage.py createsuperuser
python manage.py collectstatic
```

---

## Project Structure

```
bale_registration_bot/
│
├── config/
│   ├── settings.py          # All settings (DB, Bale, Jazzmin, Logging)
│   ├── urls.py              # Admin URL routing
│   └── wsgi.py
│
├── apps/
│   ├── registration/        # Domain models + admin
│   │   ├── models.py        # Question, FinalMessage, BotUser, RegistrationSession
│   │   ├── admin.py         # Rich admin: badges, inline answers table, bulk actions
│   │   └── migrations/
│   │       └── 0001_initial.py
│   │
│   └── bot/                 # Bot logic
│       ├── handlers.py      # ConversationHandler, validators, final-message sender
│       └── management/commands/
│           ├── runbot.py            # python manage.py runbot
│           ├── seed_sample_data.py  # python manage.py seed_sample_data
│           └── export_registrations.py  # python manage.py export_registrations
│
├── nginx/
│   └── nginx.conf           # Production nginx with HTTPS
│
├── Dockerfile
├── docker-compose.yml       # db + web + bot services
├── entrypoint.sh            # wait-for-db → migrate → collectstatic → start
├── requirements.txt
├── .env.example
└── .gitignore
```

---

## Production Deployment

### 1. Secure your `.env`
```bash
SECRET_KEY=<50+ random characters>
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
DB_PASSWORD=<strong password>
DJANGO_SUPERUSER_PASSWORD=<strong password>
```

### 2. Enable Nginx + HTTPS
```bash
# In docker-compose.yml, uncomment the nginx service
# Place TLS certs in ./nginx/certs/
# (use Certbot / Let's Encrypt)

# Update nginx.conf server_name to your domain
```

### 3. Deploy
```bash
docker compose up -d --build
docker compose logs -f bot    # watch bot logs
docker compose logs -f web    # watch web logs
```

### 4. Update without downtime
```bash
git pull
docker compose build
docker compose up -d          # rolling restart
```

---

## Extending the Bot

### Add a new question type (e.g. date)

1. Add `DATE = 'date', 'تاریخ'` to `Question.QuestionType`
2. Add a new migration: `python manage.py makemigrations`
3. Add validation in `validate_answer()` in `handlers.py`

### Add a broadcast command
Create `apps/bot/management/commands/broadcast.py` using:
```python
await context.bot.send_message(chat_id=user.bale_user_id, text=msg)
```

### Webhook instead of polling
In `runbot.py`, replace `run_polling(...)` with:
```python
await application.run_webhook(
    listen="0.0.0.0",
    port=8443,
    url_path=settings.BALE_BOT_TOKEN,
    webhook_url=f"https://yourdomain.com/{settings.BALE_BOT_TOKEN}",
)
```

---

## License

MIT — use freely.
