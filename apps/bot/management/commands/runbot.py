"""
Django management command: python manage.py runbot

Starts the Bale bot using python-telegram-bot with the Bale API base URL.
Run this as a separate process alongside the Django web server.

  production:  python manage.py runbot
  docker:      CMD ["python", "manage.py", "runbot"]
"""
import logging
import asyncio
from django.core.management.base import BaseCommand
from django.conf import settings

from telegram import BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    filters,
    PicklePersistence,
)

from apps.bot.handlers import (
    ANSWERING,
    cmd_start,
    cmd_cancel,
    cmd_restart,
    handle_answer,
    handle_unknown,
    error_handler,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Starts the Bale registration bot (polling mode)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--drop-pending',
            action='store_true',
            default=True,
            help='Drop pending updates on startup (default: True)',
        )

    def handle(self, *args, **options):
        token = settings.BALE_BOT_TOKEN
        if not token:
            self.stderr.write(self.style.ERROR(
                'BALE_BOT_TOKEN is not set in settings / .env'
            ))
            return

        self.stdout.write(self.style.SUCCESS('Starting Bale bot...'))
        asyncio.run(self._run_bot(options))

    async def _run_bot(self, options):
        # ── Build the Application pointing at Bale's API ─────────────────────
        application = (
            Application.builder()
            .token(settings.BALE_BOT_TOKEN)
            .base_url(settings.BALE_API_BASE_URL)
            .base_file_url(settings.BALE_FILE_BASE_URL)
            .build()
        )

        # ── Conversation handler ──────────────────────────────────────────────
        conv_handler = ConversationHandler(
            entry_points=[
                CommandHandler('start', cmd_start),
            ],
            states={
                ANSWERING: [
                    # Accept text messages (including button taps)
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        handle_answer,
                    ),
                    # Handle non-text messages gracefully
                    MessageHandler(
                        ~filters.TEXT & ~filters.COMMAND,
                        handle_unknown,
                    ),
                ],
            },
            fallbacks=[
                CommandHandler('cancel', cmd_cancel),
                CommandHandler('start', cmd_start),   # restart mid-flow
            ],
            allow_reentry=True,
            # Persist conversation state across restarts
            name='registration_conv',
            persistent=False,   # set to True + add PicklePersistence if needed
        )

        application.add_handler(conv_handler)

        # /restart command (outside conversation so always reachable)
        application.add_handler(CommandHandler('restart', cmd_restart))

        # Global error handler
        application.add_error_handler(error_handler)

        # ── Set bot commands ──────────────────────────────────────────────────
        async with application:
            await application.bot.set_my_commands([
                BotCommand('start', 'شروع / ادامه ثبت‌نام'),
                BotCommand('cancel', 'لغو فرآیند ثبت‌نام'),
                BotCommand('restart', 'شروع مجدد از ابتدا'),
            ])

            self.stdout.write(self.style.SUCCESS(
                f'Bot started. Polling Bale API at: {settings.BALE_API_BASE_URL}'
            ))
            logger.info('Bot started polling')

            # Start polling — drop_pending_updates clears the backlog on startup
            await application.run_polling(
                drop_pending_updates=options.get('drop_pending', True),
                allowed_updates=["message", "callback_query"],
            )
