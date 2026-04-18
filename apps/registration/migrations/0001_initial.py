"""
Initial migration for the registration app.
Generated manually — run: python manage.py migrate
"""
from django.db import migrations, models
import apps.registration.models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        # ── Question ─────────────────────────────────────────────────────────
        migrations.CreateModel(
            name='Question',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('order', models.PositiveSmallIntegerField(
                    unique=True,
                    verbose_name='ترتیب',
                    help_text='سوالات بر اساس این عدد به ترتیب پرسیده می‌شوند',
                )),
                ('text', models.TextField(verbose_name='متن سوال')),
                ('field_name', models.SlugField(
                    max_length=100,
                    unique=True,
                    verbose_name='نام فیلد',
                )),
                ('question_type', models.CharField(
                    choices=[
                        ('text', 'متن آزاد'),
                        ('phone', 'شماره تلفن'),
                        ('email', 'ایمیل'),
                        ('number', 'عدد'),
                        ('choice', 'انتخابی (دکمه‌ها)'),
                    ],
                    default='text',
                    max_length=20,
                    verbose_name='نوع سوال',
                )),
                ('choices', models.TextField(blank=True, null=True, verbose_name='گزینه‌ها')),
                ('validation_hint', models.CharField(
                    blank=True,
                    max_length=300,
                    verbose_name='راهنمای اعتبارسنجی',
                )),
                ('is_required', models.BooleanField(default=True, verbose_name='اجباری')),
                ('is_active', models.BooleanField(default=True, verbose_name='فعال')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'سوال',
                'verbose_name_plural': 'سوالات',
                'ordering': ['order'],
            },
        ),

        # ── FinalMessage ──────────────────────────────────────────────────────
        migrations.CreateModel(
            name='FinalMessage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200, verbose_name='عنوان (داخلی)')),
                ('message_type', models.CharField(
                    choices=[
                        ('text', 'پیام متنی'),
                        ('file', 'فایل / سند'),
                        ('photo', 'تصویر'),
                        ('link', 'لینک'),
                        ('text_file', 'متن + فایل'),
                        ('text_link', 'متن + لینک'),
                    ],
                    default='text',
                    max_length=20,
                    verbose_name='نوع پیام',
                )),
                ('text_content', models.TextField(blank=True, verbose_name='متن پیام')),
                ('file', models.FileField(
                    blank=True,
                    null=True,
                    upload_to=apps.registration.models.final_message_upload_to,
                    verbose_name='فایل',
                )),
                ('photo', models.ImageField(
                    blank=True,
                    null=True,
                    upload_to='final_messages/photos/',
                    verbose_name='تصویر',
                )),
                ('link_url', models.URLField(blank=True, verbose_name='آدرس لینک')),
                ('link_text', models.CharField(blank=True, max_length=200, verbose_name='متن دکمه لینک')),
                ('is_active', models.BooleanField(default=True, verbose_name='فعال')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'پیام نهایی',
                'verbose_name_plural': 'پیام‌های نهایی',
                'ordering': ['-updated_at'],
            },
        ),

        # ── BotUser ───────────────────────────────────────────────────────────
        migrations.CreateModel(
            name='BotUser',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('bale_user_id', models.BigIntegerField(
                    db_index=True,
                    unique=True,
                    verbose_name='شناسه بله',
                )),
                ('username', models.CharField(blank=True, max_length=100, verbose_name='نام کاربری')),
                ('first_name', models.CharField(blank=True, max_length=100, verbose_name='نام')),
                ('last_name', models.CharField(blank=True, max_length=100, verbose_name='نام خانوادگی')),
                ('is_registered', models.BooleanField(db_index=True, default=False, verbose_name='ثبت‌نام شده')),
                ('is_blocked', models.BooleanField(default=False, verbose_name='بلاک شده')),
                ('registered_at', models.DateTimeField(blank=True, null=True, verbose_name='زمان ثبت‌نام')),
                ('first_seen', models.DateTimeField(auto_now_add=True, verbose_name='اولین بازدید')),
                ('last_seen', models.DateTimeField(auto_now=True, verbose_name='آخرین بازدید')),
                ('notes', models.TextField(blank=True, verbose_name='یادداشت ادمین')),
            ],
            options={
                'verbose_name': 'کاربر ربات',
                'verbose_name_plural': 'کاربران ربات',
                'ordering': ['-first_seen'],
            },
        ),

        # ── RegistrationSession ───────────────────────────────────────────────
        migrations.CreateModel(
            name='RegistrationSession',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('user', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='session',
                    to='registration.botuser',
                    verbose_name='کاربر',
                )),
                ('current_question_index', models.PositiveSmallIntegerField(
                    default=0,
                    verbose_name='شماره سوال فعلی',
                )),
                ('answers', models.JSONField(default=dict, verbose_name='پاسخ‌ها')),
                ('is_completed', models.BooleanField(db_index=True, default=False, verbose_name='تکمیل شده')),
                ('started_at', models.DateTimeField(auto_now_add=True, verbose_name='شروع')),
                ('completed_at', models.DateTimeField(blank=True, null=True, verbose_name='تکمیل')),
            ],
            options={
                'verbose_name': 'جلسه ثبت‌نام',
                'verbose_name_plural': 'جلسات ثبت‌نام',
                'ordering': ['-started_at'],
            },
        ),
    ]
