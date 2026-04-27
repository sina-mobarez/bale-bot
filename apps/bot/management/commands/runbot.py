"""
Management command: python manage.py runbot

Starts the Bale bot. Two modes:
  --mode polling   (default) — long-polling, works everywhere
  --mode webhook   — webhook via simple Flask/WSGI server on --port

Library: telegram-bale-bot (pyTelegramBotAPI fork)
  Auto-detects Bale tokens (50-51 chars) and routes to tapi.bale.ai.

Examples:
  python manage.py runbot                          # polling
  python manage.py runbot --mode webhook \
    --webhook-url https://yourdomain.com/bale/     # webhook
"""
import logging
from django.core.management.base import BaseCommand
from django.conf import settings

logger = logging.getLogger(__name__)


def _make_bot():
    """Create and return a configured TeleBot instance."""
    from apps.bot.bot_factory import make_bot
    bot = make_bot(threaded=True, skip_pending=True)
    from apps.bot.handlers import register_handlers
    register_handlers(bot)
    return bot


class Command(BaseCommand):
    help = 'Start the Bale registration bot (polling or webhook)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--mode',
            choices=['polling', 'webhook'],
            default='polling',
            help='How the bot receives updates (default: polling)',
        )
        parser.add_argument(
            '--webhook-url',
            type=str,
            default='',
            help='Full public HTTPS URL for webhook mode, e.g. https://yourdomain.com/bale/',
        )
        parser.add_argument(
            '--port',
            type=int,
            default=8443,
            help='Local port for webhook listener (default: 8443)',
        )
        parser.add_argument(
            '--host',
            type=str,
            default='0.0.0.0',
            help='Local host to bind webhook listener (default: 0.0.0.0)',
        )

    def handle(self, *args, **options):
        token = settings.BALE_BOT_TOKEN
        if not token:
            self.stderr.write(self.style.ERROR(
                'BALE_BOT_TOKEN is not set. Check your .env file.'
            ))
            return

        mode = options['mode']
        bot = _make_bot()

        token_len = len(token)
        detected = 'Bale (tapi.bale.ai)' if token_len in (50, 51) else 'Telegram (api.telegram.org)'
        self.stdout.write(self.style.SUCCESS(
            f'Bot ready | token length: {token_len} → {detected} | mode: {mode}'
        ))
        logger.info(f'Bot starting in {mode} mode.')

        if mode == 'polling':
            self._start_polling(bot)
        else:
            self._start_webhook(bot, options)

    def _start_polling(self, bot):
        self.stdout.write('Starting long-polling… (Ctrl+C to stop)')
        bot.infinity_polling(
            timeout=30,
            long_polling_timeout=20,
            logger_level=logging.INFO,
            allowed_updates=['message', 'callback_query'],
        )

    def _start_webhook(self, bot, options):
        webhook_url = options['webhook_url']
        host = options['host']
        port = options['port']

        if not webhook_url:
            self.stderr.write(self.style.ERROR(
                'Webhook mode requires --webhook-url https://yourdomain.com/bale/'
            ))
            return

        # Set the webhook on Bale's side
        try:
            bot.remove_webhook()
            import time; time.sleep(0.5)
            bot.set_webhook(url=webhook_url)
            self.stdout.write(self.style.SUCCESS(f'Webhook set: {webhook_url}'))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Failed to set webhook: {e}'))
            self.stderr.write('Falling back to polling…')
            self._start_polling(bot)
            return

        # Start a minimal WSGI listener using telebot's built-in Flask integration
        try:
            from flask import Flask, request, abort
            app = Flask(__name__)

            @app.route('/' + settings.BALE_BOT_TOKEN, methods=['POST'])
            def webhook_handler():
                import telebot
                if request.headers.get('content-type') == 'application/json':
                    json_str = request.get_data(as_text=True)
                    update = telebot.types.Update.de_json(json_str)
                    bot.process_new_updates([update])
                    return ''
                abort(403)

            @app.route('/health')
            def health():
                return 'ok'

            self.stdout.write(
                f'Webhook listener on {host}:{port}{chr(10)}'
                f'Endpoint: POST /{settings.BALE_BOT_TOKEN}'
            )
            app.run(host=host, port=port, debug=False, use_reloader=False)

        except ImportError:
            self.stderr.write(self.style.WARNING(
                'Flask is not installed. Install it with: pip install flask\n'
                'Falling back to polling mode.'
            ))
            self._start_polling(bot)
