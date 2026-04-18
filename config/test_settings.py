"""
Test settings — uses in-memory SQLite so no Postgres needed for running tests.
"""
from config.settings import *   # noqa: F401, F403

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

SECRET_KEY = 'test-secret-key-for-pytest-1234567890'
DEBUG = True
BALE_BOT_TOKEN = 'test_token_50_chars_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
BALE_API_BASE_URL = 'https://tapi.bale.ai/bot'
BALE_FILE_BASE_URL = 'https://tapi.bale.ai/file/bot'
ALLOWED_HOSTS = ['*']

# No compression in tests
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
}

# Silence logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': True,
    'handlers': {'null': {'class': 'logging.NullHandler'}},
    'root': {'handlers': ['null']},
}
