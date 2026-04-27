"""
Shared bot factory used by both the runbot command and Celery tasks.
Always points to tapi.bale.ai when BALE_API_BASE_URL is configured.
"""
import telebot
from telebot import apihelper
from django.conf import settings


def make_bot(**kwargs) -> telebot.TeleBot:
    base_url = getattr(settings, 'BALE_API_BASE_URL', '')
    file_url = getattr(settings, 'BALE_FILE_BASE_URL', '')

    if base_url:
        apihelper.API_URL = base_url.rstrip('/') + '{0}/{1}'
    if file_url:
        apihelper.FILE_URL = file_url.rstrip('/') + '{0}/{1}'

    return telebot.TeleBot(
        settings.BALE_BOT_TOKEN,
        parse_mode=None,
        validate_token=False,
        **kwargs,
    )
