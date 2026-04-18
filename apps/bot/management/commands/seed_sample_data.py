"""
Management command: python manage.py seed_sample_data

Creates sample questions and a sample final message so you can test
the bot immediately after setup without clicking through the admin.

Safe to run multiple times — uses get_or_create.
"""
from django.core.management.base import BaseCommand
from django.db import transaction


SAMPLE_QUESTIONS = [
    {
        'order': 1,
        'text': '👤 لطفاً نام و نام خانوادگی خود را وارد کنید:',
        'field_name': 'full_name',
        'question_type': 'text',
        'is_required': True,
    },
    {
        'order': 2,
        'text': '📱 شماره موبایل خود را وارد کنید:\n(مثال: 09123456789)',
        'field_name': 'phone',
        'question_type': 'phone',
        'is_required': True,
        'validation_hint': '⚠️ شماره موبایل معتبر وارد کنید. مثال: 09123456789',
    },
    {
        'order': 3,
        'text': '📧 آدرس ایمیل خود را وارد کنید:',
        'field_name': 'email',
        'question_type': 'email',
        'is_required': True,
        'validation_hint': '⚠️ ایمیل معتبر وارد کنید. مثال: name@example.com',
    },
    {
        'order': 4,
        'text': '🏙️ شهر محل سکونت خود را انتخاب کنید:',
        'field_name': 'city',
        'question_type': 'choice',
        'choices': 'تهران\nاصفهان\nشیراز\nمشهد\nتبریز\nسایر',
        'is_required': True,
    },
    {
        'order': 5,
        'text': '💼 حوزه فعالیت شما چیست؟',
        'field_name': 'field_of_work',
        'question_type': 'text',
        'is_required': False,
    },
]

SAMPLE_FINAL_MESSAGE = {
    'title': 'پیام خوشامدگویی پیش‌فرض',
    'message_type': 'text_link',
    'text_content': (
        '🎉 *ثبت‌نام شما با موفقیت انجام شد!*\n\n'
        'از اینکه وقت گذاشتید و فرم را تکمیل کردید متشکریم.\n\n'
        'تیم ما به زودی با شما تماس خواهد گرفت.\n\n'
        '_با تشکر از همراهی شما_ 🙏'
    ),
    'link_url': 'https://example.com',
    'link_text': '🌐 مشاهده وبسایت',
    'is_active': True,
}


class Command(BaseCommand):
    help = 'Seeds the database with sample questions and a final message for testing'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Delete existing questions and final messages before seeding',
        )

    def handle(self, *args, **options):
        from apps.registration.models import Question, FinalMessage

        with transaction.atomic():
            if options['reset']:
                deleted_q, _ = Question.objects.all().delete()
                deleted_fm, _ = FinalMessage.objects.all().delete()
                self.stdout.write(self.style.WARNING(
                    f'Deleted {deleted_q} questions and {deleted_fm} final messages.'
                ))

            # ── Seed questions ────────────────────────────────────────────────
            created_count = 0
            for q_data in SAMPLE_QUESTIONS:
                obj, created = Question.objects.update_or_create(
                    field_name=q_data['field_name'],
                    defaults=q_data,
                )
                if created:
                    created_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'  ✅ Created question [{obj.order}]: {obj.field_name}')
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(f'  ↩ Updated question [{obj.order}]: {obj.field_name}')
                    )

            # ── Seed final message ────────────────────────────────────────────
            fm, fm_created = FinalMessage.objects.update_or_create(
                title=SAMPLE_FINAL_MESSAGE['title'],
                defaults=SAMPLE_FINAL_MESSAGE,
            )
            if fm_created:
                self.stdout.write(self.style.SUCCESS(f'  ✅ Created final message: {fm.title}'))
            else:
                self.stdout.write(self.style.WARNING(f'  ↩ Updated final message: {fm.title}'))

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'Done! {len(SAMPLE_QUESTIONS)} questions and 1 final message are ready.\n'
            f'Start the bot with:  python manage.py runbot'
        ))
