# Celery Setup Guide

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Update `.env` file with Redis configuration:
```bash
# Add these lines to your .env file
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

## Running Redis

### Using Docker:
```bash
docker run -d -p 6379:6379 redis:alpine
```

### Or install Redis locally:
```bash
# Ubuntu/Debian
sudo apt-get install redis-server
sudo systemctl start redis

# macOS
brew install redis
brew services start redis
```

## Running Celery

### 1. Run Celery Worker:
```bash
celery -A config worker --loglevel=info
```

### 2. Run Celery Beat (Scheduler):
```bash
celery -A config beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

### Or run both together (for development):
```bash
celery -A config worker --beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

## Database Migrations

Run migrations to create Celery Beat tables:
```bash
python manage.py migrate
```

## Setting Up Scheduled Messages

### Option 1: Using Django Admin

1. Go to Django Admin: http://localhost:8000/admin/
2. Navigate to "Periodic Tasks" under "Django Celery Beat"
3. Click "Add Periodic Task"
4. Configure:
   - **Name**: Send Scheduled Messages
   - **Task**: `apps.registration.send_scheduled_messages`
   - **Interval**: Create a new interval (e.g., every 1 minute)
   - **Enabled**: ✓

### Option 2: Using Django Shell

```python
from django_celery_beat.models import PeriodicTask, IntervalSchedule

# Create an interval schedule (every 1 minute)
schedule, created = IntervalSchedule.objects.get_or_create(
    every=1,
    period=IntervalSchedule.MINUTES,
)

# Create the periodic task
PeriodicTask.objects.create(
    interval=schedule,
    name='Send Scheduled Messages',
    task='apps.registration.send_scheduled_messages',
)
```

## Creating Scheduled Messages

1. Go to Django Admin
2. Navigate to "Scheduled Messages" under "Registration"
3. Click "Add Scheduled Message"
4. Fill in:
   - Title
   - Message Type (Text, File, Photo, Link)
   - Content (based on type)
   - Scheduled Time (when to send)
5. Save

The message will be automatically sent to all registered users at the scheduled time.

## Admin Actions

- **Send Now**: Select messages and use the "Send Now" action to send them immediately

## Production Deployment

### Using Supervisor (Recommended)

Create `/etc/supervisor/conf.d/celery.conf`:

```ini
[program:celery-worker]
command=/path/to/venv/bin/celery -A config worker --loglevel=info
directory=/path/to/project
user=www-data
autostart=true
autorestart=true
stdout_logfile=/var/log/celery/worker.log
stderr_logfile=/var/log/celery/worker_error.log

[program:celery-beat]
command=/path/to/venv/bin/celery -A config beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler
directory=/path/to/project
user=www-data
autostart=true
autorestart=true
stdout_logfile=/var/log/celery/beat.log
stderr_logfile=/var/log/celery/beat_error.log
```

Then:
```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start celery-worker celery-beat
```

### Using systemd

Create `/etc/systemd/system/celery-worker.service`:

```ini
[Unit]
Description=Celery Worker
After=network.target

[Service]
Type=forking
User=www-data
Group=www-data
WorkingDirectory=/path/to/project
ExecStart=/path/to/venv/bin/celery -A config worker --loglevel=info --detach
Restart=always

[Install]
WantedBy=multi-user.target
```

Create `/etc/systemd/system/celery-beat.service`:

```ini
[Unit]
Description=Celery Beat
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/path/to/project
ExecStart=/path/to/venv/bin/celery -A config beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler
Restart=always

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable celery-worker celery-beat
sudo systemctl start celery-worker celery-beat
```

## Monitoring

Check Celery status:
```bash
celery -A config inspect active
celery -A config inspect stats
```

View logs:
```bash
# Worker logs
tail -f /var/log/celery/worker.log

# Beat logs
tail -f /var/log/celery/beat.log
```

## Troubleshooting

### Redis connection error
- Make sure Redis is running: `redis-cli ping` (should return "PONG")
- Check Redis URL in `.env` file

### Tasks not executing
- Check if Celery Beat is running
- Verify periodic task is enabled in Django Admin
- Check Celery logs for errors

### Messages not sending
- Verify `BALE_BOT_TOKEN` is set in `.env`
- Check that users are registered (`is_registered=True`)
- Check Celery worker logs for errors
