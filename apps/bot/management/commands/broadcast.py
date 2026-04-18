"""
Management command: python manage.py broadcast

Sends a message to all registered (or all) Bale bot users.

Usage examples:
  # Send text to all registered users
  python manage.py broadcast --message "🎉 اطلاعیه مهم: سیستم فردا آپدیت می‌شود."

  # Send to ALL users (including incomplete registrations)
  python manage.py broadcast --message "سلام!" --all-users

  # Send a file
  python manage.py broadcast --file /path/to/report.pdf --message "گزارش ماهانه"

  # Dry run — show who would receive the message without sending
  python manage.py broadcast --message "تست" --dry-run

  # Delay between messages to avoid rate limiting (milliseconds)
  python manage.py broadcast --message "..." --delay 500
"""
import time
import os
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings


class Command(BaseCommand):
    help = 'Broadcast a message to all registered Bale users'

    def add_arguments(self, parser):
        parser.add_argument(
            '--message', '-m',
            type=str,
            default='',
            help='Text message to send (supports Markdown)',
        )
        parser.add_argument(
            '--file', '-f',
            type=str,
            default=None,
            help='Path to a file to send as document',
        )
        parser.add_argument(
            '--all-users',
            action='store_true',
            default=False,
            help='Send to all users, not just registered ones',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            default=False,
            help='List recipients without actually sending',
        )
        parser.add_argument(
            '--delay',
            type=int,
            default=200,
            help='Delay between each message in milliseconds (default: 200)',
        )
        parser.add_argument(
            '--user-id',
            type=int,
            default=None,
            help='Send only to a specific bale_user_id (for testing)',
        )

    def handle(self, *args, **options):
        from apps.registration.models import BotUser

        message_text = options['message'].strip()
        file_path = options['file']
        dry_run = options['dry_run']
        delay_ms = options['delay']
        target_id = options['user_id']

        if not message_text and not file_path:
            raise CommandError('Provide --message and/or --file.')

        if file_path and not os.path.isfile(file_path):
            raise CommandError(f'File not found: {file_path}')

        # ── Build recipient queryset ──────────────────────────────────────────
        qs = BotUser.objects.filter(is_blocked=False)
        if target_id:
            qs = qs.filter(bale_user_id=target_id)
        elif not options['all_users']:
            qs = qs.filter(is_registered=True)

        total = qs.count()
        if total == 0:
            self.stdout.write(self.style.WARNING('No recipients found.'))
            return

        self.stdout.write(
            f'{"[DRY RUN] " if dry_run else ""}Broadcasting to {total} users '
            f'(delay: {delay_ms}ms between messages)'
        )

        if dry_run:
            for user in qs:
                self.stdout.write(f'  → {user} (id={user.bale_user_id})')
            self.stdout.write(self.style.SUCCESS(f'Dry run complete. {total} recipients.'))
            return

        # ── Configure bot ─────────────────────────────────────────────────────
        import telebot
        from telebot import apihelper

        token = settings.BALE_BOT_TOKEN
        base_url = settings.BALE_API_BASE_URL
        if base_url and base_url != 'https://tapi.bale.ai/bot':
            apihelper.API_URL = base_url.rstrip('/') + '/{0}/{1}'

        bot = telebot.TeleBot(token, validate_token=False)

        # ── Send ──────────────────────────────────────────────────────────────
        sent = 0
        failed = 0
        blocked = []

        for user in qs.iterator():
            chat_id = user.bale_user_id
            try:
                if file_path:
                    with open(file_path, 'rb') as f:
                        caption = message_text or None
                        bot.send_document(
                            chat_id, f,
                            caption=caption,
                            parse_mode='Markdown' if caption else None,
                            visible_file_name=os.path.basename(file_path),
                        )
                elif message_text:
                    bot.send_message(chat_id, message_text, parse_mode='Markdown')

                sent += 1
                self.stdout.write(f'  ✅ Sent to {user} (id={chat_id})')

            except Exception as e:
                failed += 1
                err_str = str(e).lower()
                if 'forbidden' in err_str or 'blocked' in err_str or 'deactivated' in err_str:
                    blocked.append(user)
                    self.stdout.write(
                        self.style.WARNING(f'  ⛔ Blocked/deactivated: {user} (id={chat_id})')
                    )
                else:
                    self.stdout.write(
                        self.style.ERROR(f'  ❌ Failed for {user} (id={chat_id}): {e}')
                    )

            # Rate-limit delay
            if delay_ms > 0:
                time.sleep(delay_ms / 1000)

        # Auto-block users who have blocked the bot
        if blocked:
            ids = [u.pk for u in blocked]
            BotUser.objects.filter(pk__in=ids).update(is_blocked=True)
            self.stdout.write(
                self.style.WARNING(f'Auto-blocked {len(blocked)} users who blocked the bot.')
            )

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'Broadcast complete: {sent} sent, {failed} failed (of {total} total).'
        ))
