"""
Registration app models.

Models:
  - Question       : A question asked during registration (ordered, typed)
  - FinalMessage   : What is sent to the user after successful registration
  - BotUser        : A Bale user who interacted with the bot
  - RegistrationSession : Tracks a user's progress through the question flow
"""
import os
from django.db import models
from django.utils import timezone
from django.core.validators import FileExtensionValidator


class Question(models.Model):
    """
    Represents a single question that the bot asks during registration.
    Questions are asked in ascending `order`.
    """

    class QuestionType(models.TextChoices):
        TEXT = 'text', 'متن آزاد'
        PHONE = 'phone', 'شماره تلفن'
        EMAIL = 'email', 'ایمیل'
        NUMBER = 'number', 'عدد'
        CHOICE = 'choice', 'انتخابی (دکمه‌ها)'

    order = models.PositiveSmallIntegerField(
        verbose_name='ترتیب',
        unique=True,
        help_text='سوالات بر اساس این عدد به ترتیب پرسیده می‌شوند',
    )
    text = models.TextField(
        verbose_name='متن سوال',
        help_text='متنی که برای کاربر ارسال می‌شود',
    )
    field_name = models.SlugField(
        verbose_name='نام فیلد',
        max_length=100,
        unique=True,
        help_text='شناسه یکتا برای ذخیره پاسخ (فقط حروف لاتین و آندرلاین)',
    )
    question_type = models.CharField(
        verbose_name='نوع سوال',
        max_length=20,
        choices=QuestionType.choices,
        default=QuestionType.TEXT,
    )
    choices = models.TextField(
        verbose_name='گزینه‌ها',
        blank=True,
        null=True,
        help_text='برای نوع "انتخابی": هر گزینه در یک خط. مثال:\nگزینه ۱\nگزینه ۲',
    )
    validation_hint = models.CharField(
        verbose_name='راهنمای اعتبارسنجی',
        max_length=300,
        blank=True,
        help_text='در صورت ورود نامعتبر این پیام نشان داده می‌شود',
    )
    is_required = models.BooleanField(verbose_name='اجباری', default=True)
    is_active = models.BooleanField(verbose_name='فعال', default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'سوال'
        verbose_name_plural = 'سوالات'
        ordering = ['order']

    def __str__(self):
        return f'[{self.order}] {self.text[:60]}'

    def get_choices_list(self):
        """Return list of choice strings, or empty list."""
        if self.question_type == self.QuestionType.CHOICE and self.choices:
            return [c.strip() for c in self.choices.splitlines() if c.strip()]
        return []


def final_message_upload_to(instance, filename):
    ext = os.path.splitext(filename)[1]
    return f'final_messages/{instance.pk or "new"}{ext}'


class FinalMessage(models.Model):
    """
    The message sent to the user after successful registration.
    Only ONE instance should be active at a time.
    """

    class MessageType(models.TextChoices):
        TEXT = 'text', 'پیام متنی'
        FILE = 'file', 'فایل / سند'
        PHOTO = 'photo', 'تصویر'
        LINK = 'link', 'لینک'
        TEXT_AND_FILE = 'text_file', 'متن + فایل'
        TEXT_AND_LINK = 'text_link', 'متن + لینک'

    title = models.CharField(
        verbose_name='عنوان (داخلی)',
        max_length=200,
        help_text='فقط برای مدیریت داخلی — کاربر نمی‌بیند',
    )
    message_type = models.CharField(
        verbose_name='نوع پیام',
        max_length=20,
        choices=MessageType.choices,
        default=MessageType.TEXT,
    )
    text_content = models.TextField(
        verbose_name='متن پیام',
        blank=True,
        help_text='از Markdown پشتیبانی می‌شود (*bold*, _italic_, etc.)',
    )
    file = models.FileField(
        verbose_name='فایل',
        upload_to=final_message_upload_to,
        blank=True,
        null=True,
        help_text='فایل ارسالی به کاربر پس از ثبت‌نام',
    )
    photo = models.ImageField(
        verbose_name='تصویر',
        upload_to='final_messages/photos/',
        blank=True,
        null=True,
    )
    link_url = models.URLField(
        verbose_name='آدرس لینک',
        blank=True,
        help_text='مثال: https://example.com',
    )
    link_text = models.CharField(
        verbose_name='متن دکمه لینک',
        max_length=200,
        blank=True,
        help_text='متن دکمه inline — اگر خالی باشد لینک به صورت متن ارسال می‌شود',
    )
    is_active = models.BooleanField(
        verbose_name='فعال',
        default=True,
        help_text='فقط یک پیام می‌تواند فعال باشد',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'پیام نهایی'
        verbose_name_plural = 'پیام‌های نهایی'
        ordering = ['-updated_at']

    def __str__(self):
        status = '✅ فعال' if self.is_active else '❌ غیرفعال'
        return f'{self.title} ({status})'

    def save(self, *args, **kwargs):
        """Ensure only one FinalMessage is active at a time."""
        if self.is_active:
            FinalMessage.objects.exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)


class BotUser(models.Model):
    """
    Represents a user who started the bot.
    """
    bale_user_id = models.BigIntegerField(
        verbose_name='شناسه بله',
        unique=True,
        db_index=True,
    )
    username = models.CharField(verbose_name='نام کاربری', max_length=100, blank=True)
    first_name = models.CharField(verbose_name='نام', max_length=100, blank=True)
    last_name = models.CharField(verbose_name='نام خانوادگی', max_length=100, blank=True)
    is_registered = models.BooleanField(verbose_name='ثبت‌نام شده', default=False, db_index=True)
    is_blocked = models.BooleanField(verbose_name='بلاک شده', default=False)
    registered_at = models.DateTimeField(verbose_name='زمان ثبت‌نام', null=True, blank=True)
    first_seen = models.DateTimeField(verbose_name='اولین بازدید', auto_now_add=True)
    last_seen = models.DateTimeField(verbose_name='آخرین بازدید', auto_now=True)
    notes = models.TextField(verbose_name='یادداشت ادمین', blank=True)

    class Meta:
        verbose_name = 'کاربر ربات'
        verbose_name_plural = 'کاربران ربات'
        ordering = ['-first_seen']

    def __str__(self):
        name = f'{self.first_name} {self.last_name}'.strip() or f'User_{self.bale_user_id}'
        return f'{name} (@{self.username})' if self.username else name

    @property
    def full_name(self):
        return f'{self.first_name} {self.last_name}'.strip()


class RegistrationSession(models.Model):
    """
    Tracks a user's progress through the registration question flow.
    answers field: {"field_name": "user_answer", ...}
    """
    user = models.OneToOneField(
        BotUser,
        on_delete=models.CASCADE,
        related_name='session',
        verbose_name='کاربر',
    )
    current_question_index = models.PositiveSmallIntegerField(
        verbose_name='شماره سوال فعلی',
        default=0,
    )
    answers = models.JSONField(
        verbose_name='پاسخ‌ها',
        default=dict,
        help_text='JSON ذخیره‌سازی پاسخ‌های کاربر',
    )
    is_completed = models.BooleanField(verbose_name='تکمیل شده', default=False, db_index=True)
    started_at = models.DateTimeField(verbose_name='شروع', auto_now_add=True)
    completed_at = models.DateTimeField(verbose_name='تکمیل', null=True, blank=True)

    class Meta:
        verbose_name = 'جلسه ثبت‌نام'
        verbose_name_plural = 'جلسات ثبت‌نام'
        ordering = ['-started_at']

    def __str__(self):
        status = '✅ تکمیل' if self.is_completed else f'⏳ سوال {self.current_question_index + 1}'
        return f'{self.user} — {status}'

    def get_answers_display(self):
        """Returns answers as a readable multi-line string."""
        if not self.answers:
            return 'بدون پاسخ'
        lines = []
        for k, v in self.answers.items():
            lines.append(f'{k}: {v}')
        return '\n'.join(lines)
