# 🤖 Bale Registration Bot

A **production-ready** Django bot for [Bale Messenger](https://bale.ai) that:

- Guides users through a **configurable question flow** and registers them
- **Validates** answers per type: phone, email, number, multiple-choice with buttons
- Sends a **customizable final message** on completion — text, file, photo, link, or combos
- Provides a rich **Django Admin panel** (Jazzmin) with live stats, answer tables, CSV export
- Notifies an **admin Bale chat** on every new registration (optional)
- Supports **polling** and **webhook** modes
- Ships with **97 passing tests**, Docker Compose, nginx config, and a Makefile

---

## Table of Contents

1. [Architecture](#architecture)
2. [Quick Start — Docker](#quick-start--docker)
3. [Quick Start — Local](#quick-start--local)
4. [Admin Panel Guide](#admin-panel-guide)
5. [Bot Commands](#bot-commands)
6. [Environment Variables](#environment-variables)
7. [Management Commands](#management-commands)
8. [Running Tests](#running-tests)
9. [Project Structure](#project-structure)
10. [Production Deployment](#production-deployment)
11. [Extending the Bot](#extending-the-bot)

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Docker Compose                        │
│                                                         │
│  ┌──────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │PostgreSQL│◄───│  Django Web  │    │  Bale Bot    │  │
│  │  (db)    │    │  (Gunicorn)  │    │  (polling)   │  │
│  └──────────┘    │  port 8000   │    │              │  │
│        ▲         └──────────────┘    └──────────────┘  │
│        └──────────────────┴────────────────────────────┘│
│                    shared DB + media                     │
└─────────────────────────────────────────────────────────┘
              ▲ (optional)
         ┌──────────┐
         │  Nginx   │  HTTPS termination, static/media
         │  80/443  │
         └──────────┘
```

**Key tech decisions:**

| Concern | Choice | Why |
|---|---|---|
| Bot library | `telegram-bale-bot` (pyTelegramBotAPI fork) | Built for Bale; auto-routes to `tapi.bale.ai` by token length; no unsupported API calls |
| State machine | DB-driven via `RegistrationSession.current_question_index` | Survives restarts; no in-memory state |
| Admin UI | Django Admin + Jazzmin | RTL-friendly, live stats, CSV export, progress bars |
| Web server | Gunicorn + WhiteNoise | Production-ready, serves static files directly |

---

## Quick Start — Docker

### Prerequisites
- Docker ≥ 24 and Docker Compose v2
- A Bale bot token from **@BotFather** in Bale messenger

```bash
# 1. Clone / unzip the project
cd bale_registration_bot

# 2. Configure environment
cp .env.example .env
nano .env
# Required: BALE_BOT_TOKEN, DB_PASSWORD, SECRET_KEY

# 3. Build and start all services
docker compose up -d --build

# 4. Seed sample questions (optional but recommended for first run)
docker compose exec bot python manage.py seed_sample_data

# 5. Open admin panel
open http://localhost:8000/admin/
# Login: DJANGO_SUPERUSER_USERNAME / DJANGO_SUPERUSER_PASSWORD from .env
```

The bot starts polling immediately. Logs:
```bash
docker compose logs -f bot   # bot activity
docker compose logs -f web   # admin panel
```

---

## Quick Start — Local

```bash
# 1. Create virtual environment
python -m venv .venv && source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure
cp .env.example .env
# Edit .env — set BALE_BOT_TOKEN + DB credentials

# 4. Migrate and seed
python manage.py migrate
python manage.py createsuperuser
python manage.py seed_sample_data

# 5. Terminal A — Admin web
python manage.py runserver

# 6. Terminal B — Bale bot
python manage.py runbot
```

Or use the Makefile:
```bash
make install && make migrate && make seed
make run-web    # Terminal A
make run-bot    # Terminal B
```

---

## Admin Panel Guide

Open `http://localhost:8000/admin/` and log in.

### Stats Dashboard

The **کاربران ربات** (BotUser) page shows a live stats bar at the top:

| Card | Meaning |
|---|---|
| کل کاربران | Total users who ever pressed /start |
| ثبت‌نام کامل | Completed registrations |
| در حال ثبت‌نام | Active sessions in progress |
| بلاک شده | Blocked users |
| ثبت‌نام امروز | New completions today |
| نرخ تکمیل | Completion % |

### Managing Questions (`سوالات`)

| Field | Description |
|---|---|
| **ترتیب** | Questions are asked in ascending order (1, 2, 3…) |
| **متن سوال** | The message text sent to the user |
| **نام فیلد** | Slug key used to store the answer, e.g. `full_name` |
| **نوع سوال** | `text` / `phone` / `email` / `number` / `choice` |
| **گزینه‌ها** | For `choice` type: one option per line; shown as keyboard buttons |
| **راهنمای اعتبارسنجی** | Error message shown on invalid input |
| **اجباری** | If checked, blank answers are rejected |
| **فعال** | Toggle to include/exclude without deleting |

### Managing the Final Message (`پیام‌های نهایی`)

Choose a message type:

| Type | What is sent |
|---|---|
| `متن` | Plain Markdown text |
| `فایل` | File attachment (any format) |
| `تصویر` | Photo |
| `لینک` | Text + inline URL button |
| `متن + فایل` | Text then file |
| `متن + لینک` | Text with inline link button |

> ⚠️ Only **one** FinalMessage can be active. Activating a new one auto-deactivates the previous.

### User Management

- **کاربران ربات** — full user list; click any user to see their session and answers table
- **Bulk actions** — Export CSV, block, unblock, reset registration
- **📥 خروجی CSV همه کاربران** button — exports all users at once (top of list page)

---

## Bot Commands

| Command | Description |
|---|---|
| `/start` | Begin registration (or resume if in progress) |
| `/cancel` | Cancel and discard current flow |
| `/restart` | Hard reset — wipes session and starts from Q1 |

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `SECRET_KEY` | ✅ | — | Django secret key (50+ random chars) |
| `DEBUG` | | `False` | Enable Django debug mode |
| `ALLOWED_HOSTS` | ✅ | `localhost` | Comma-separated host list |
| `BALE_BOT_TOKEN` | ✅ | — | Token from @BotFather in Bale |
| `BALE_API_BASE_URL` | | `https://tapi.bale.ai/bot` | Override only if using a custom Bale API |
| `BALE_FILE_BASE_URL` | | `https://tapi.bale.ai/file/bot` | Override only if using a custom Bale file API |
| `BALE_ADMIN_CHAT_ID` | | — | Your Bale user ID — receive a ping on each new registration |
| `DB_NAME` | ✅ | `bale_bot_db` | PostgreSQL database name |
| `DB_USER` | ✅ | `bale_bot_user` | PostgreSQL username |
| `DB_PASSWORD` | ✅ | — | PostgreSQL password |
| `DB_HOST` | | `db` | DB host (`localhost` for local dev) |
| `DB_PORT` | | `5432` | DB port |
| `DJANGO_SUPERUSER_USERNAME` | | `admin` | Auto-created on first Docker startup |
| `DJANGO_SUPERUSER_PASSWORD` | | — | Auto-created on first Docker startup |
| `DJANGO_SUPERUSER_EMAIL` | | — | Auto-created on first Docker startup |

---

## Management Commands

```bash
# ── Bot ──────────────────────────────────────────────────────────
# Start polling (default)
python manage.py runbot

# Start in webhook mode
python manage.py runbot --mode webhook \
  --webhook-url https://yourdomain.com/bale/ \
  --port 8443

# ── Data ─────────────────────────────────────────────────────────
# Seed 5 sample questions + a final message
python manage.py seed_sample_data

# Re-seed (clears all existing first)
python manage.py seed_sample_data --reset

# Export all completed registrations to CSV
python manage.py export_registrations
python manage.py export_registrations --output /tmp/users.csv

# Broadcast a message to all registered users
python manage.py broadcast --message "📢 اطلاعیه جدید"

# Broadcast a file
python manage.py broadcast --file /path/to/doc.pdf --message "فایل ضمیمه"

# Dry-run (shows recipients without sending)
python manage.py broadcast --message "تست" --dry-run

# ── Django ───────────────────────────────────────────────────────
python manage.py migrate
python manage.py createsuperuser
python manage.py collectstatic
```

---

## Running Tests

No database server needed — tests use in-memory SQLite:

```bash
# Install test deps (already in requirements.txt)
pip install pytest pytest-django

# Run all tests
python -m pytest tests/ -v

# Run a specific test file
python -m pytest tests/test_handlers.py -v

# Run with coverage
pip install pytest-cov
python -m pytest tests/ --cov=apps --cov-report=term-missing
```

**97 tests** covering:

| Test file | What it covers |
|---|---|
| `test_bot.py` | Models, validators, flow helpers, admin CSV export, management commands (Django `TestCase`) |
| `test_models.py` | Model constraints, FinalMessage single-active rule, session/user relationships (pytest-django) |
| `test_handlers.py` | Validator edge cases (parametrize), DB helpers, full registration flow simulation |

---

## Project Structure

```
bale_registration_bot/
│
├── config/
│   ├── settings.py          # All settings: DB, Bale, Jazzmin, Logging
│   ├── test_settings.py     # Test overrides (SQLite in-memory)
│   ├── urls.py              # Admin + export URL routing
│   └── wsgi.py
│
├── apps/
│   ├── registration/        # Domain: models + admin
│   │   ├── models.py        # Question, FinalMessage, BotUser, RegistrationSession
│   │   ├── admin.py         # Jazzmin admin: stats bar, inline answers, CSV export
│   │   ├── migrations/
│   │   │   └── 0001_initial.py
│   │   └── templates/
│   │       └── admin/registration/botuser/
│   │           └── change_list.html  # Stats bar + Export All button
│   │
│   └── bot/                 # Bot logic + management commands
│       ├── handlers.py      # Rate limiter, DB state machine, final-message sender,
│       │                    # admin notifications, register_handlers()
│       └── management/commands/
│           ├── runbot.py              # polling or webhook mode
│           ├── seed_sample_data.py    # seed 5 sample Q's + final message
│           ├── export_registrations.py # CSV export to file
│           └── broadcast.py          # bulk message sender with rate limiting
│
├── tests/
│   ├── test_bot.py          # Django TestCase — models, validators, admin, commands
│   ├── test_models.py       # pytest — model constraints and rules
│   └── test_handlers.py     # pytest — validators (parametrized), DB helpers, flows
│
├── nginx/nginx.conf         # Production HTTPS config with security headers
├── Dockerfile
├── docker-compose.yml       # db + web + bot services with health checks
├── entrypoint.sh            # wait-for-db → migrate → collectstatic → start
├── Makefile                 # Developer convenience targets
├── pytest.ini
├── conftest.py              # Shared pytest fixtures
├── requirements.txt
├── .env.example
└── .gitignore
```

---

## Production Deployment

### 1. Harden `.env`

```bash
SECRET_KEY=<50+ random characters, e.g. from: python -c "import secrets; print(secrets.token_urlsafe(50))">
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
DB_PASSWORD=<strong unique password>
DJANGO_SUPERUSER_PASSWORD=<strong unique password>
BALE_ADMIN_CHAT_ID=<your Bale user ID, find it with @userinfobot>
```

### 2. Enable Nginx + HTTPS

```bash
# 1. Uncomment nginx service in docker-compose.yml
# 2. Replace yourdomain.com in nginx/nginx.conf
# 3. Place TLS certificates in ./nginx/certs/
#    (use Certbot: certbot certonly --standalone -d yourdomain.com)

mkdir -p nginx/certs
cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem nginx/certs/
cp /etc/letsencrypt/live/yourdomain.com/privkey.pem nginx/certs/
```

### 3. Deploy

```bash
docker compose up -d --build
docker compose logs -f        # watch all logs

# Verify
curl http://localhost:8000/admin/login/   # should return 200
```

### 4. Zero-downtime updates

```bash
git pull
docker compose build
docker compose up -d          # rolling restart
```

---

## Extending the Bot

### Add a new question type (e.g. date)

1. Add `DATE = 'date', 'تاریخ'` to `Question.QuestionType` in `models.py`
2. `python manage.py makemigrations && python manage.py migrate`
3. Add a branch in `validate_answer()` in `handlers.py`

### Switch to webhook mode

```bash
# In production with a public HTTPS domain:
python manage.py runbot \
  --mode webhook \
  --webhook-url https://yourdomain.com/YOUR_BOT_TOKEN/ \
  --port 8443

# Requires: pip install flask
# In Docker: set CMD to ["python", "manage.py", "runbot", "--mode", "webhook", ...]
```

### Add a welcome image

In `FinalMessage`, set `message_type = photo`, upload a photo, and add a caption.

### Broadcast to all users

```bash
python manage.py broadcast --message "📢 پیام مهم" --delay 300
python manage.py broadcast --file report.pdf --all-users
```

---

## License

MIT — use freely, credit appreciated.
