"""
Admin configuration for the registration app.
Provides a rich admin UI for managing questions, final messages, and user registrations.
"""
from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.db.models import Count
from django.urls import reverse

from .models import Question, FinalMessage, BotUser, RegistrationSession


# ─── Question ─────────────────────────────────────────────────────────────────

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = (
        'order_badge', 'text_preview', 'field_name',
        'question_type_badge', 'is_required', 'is_active',
    )
    list_display_links = ('order_badge', 'text_preview')
    list_editable = ('is_active',)
    list_filter = ('question_type', 'is_required', 'is_active')
    search_fields = ('text', 'field_name')
    ordering = ('order',)
    fieldsets = (
        ('محتوا', {
            'fields': ('order', 'text', 'field_name', 'question_type', 'choices'),
        }),
        ('اعتبارسنجی و تنظیمات', {
            'fields': ('validation_hint', 'is_required', 'is_active'),
        }),
    )
    readonly_fields = ('created_at', 'updated_at')

    def order_badge(self, obj):
        return format_html(
            '<span style="background:#0d6efd;color:white;padding:2px 8px;'
            'border-radius:10px;font-weight:bold">{}</span>',
            obj.order
        )
    order_badge.short_description = 'ترتیب'
    order_badge.admin_order_field = 'order'

    def text_preview(self, obj):
        return obj.text[:80] + '...' if len(obj.text) > 80 else obj.text
    text_preview.short_description = 'متن سوال'

    def question_type_badge(self, obj):
        colors = {
            'text': '#6c757d',
            'phone': '#198754',
            'email': '#0dcaf0',
            'number': '#fd7e14',
            'choice': '#6f42c1',
        }
        color = colors.get(obj.question_type, '#6c757d')
        return format_html(
            '<span style="background:{};color:white;padding:2px 8px;border-radius:10px">{}</span>',
            color, obj.get_question_type_display()
        )
    question_type_badge.short_description = 'نوع'


# ─── FinalMessage ─────────────────────────────────────────────────────────────

@admin.register(FinalMessage)
class FinalMessageAdmin(admin.ModelAdmin):
    list_display = ('title', 'message_type_badge', 'is_active_badge', 'updated_at')
    list_display_links = ('title',)
    list_filter = ('message_type', 'is_active')
    search_fields = ('title', 'text_content')
    readonly_fields = ('created_at', 'updated_at', 'preview_section')
    fieldsets = (
        ('اطلاعات اصلی', {
            'fields': ('title', 'message_type', 'is_active'),
        }),
        ('محتوا', {
            'fields': ('text_content', 'file', 'photo', 'link_url', 'link_text'),
            'description': 'بسته به نوع پیام، فیلدهای مربوطه را پر کنید',
        }),
        ('پیش‌نمایش', {
            'fields': ('preview_section',),
            'classes': ('collapse',),
        }),
        ('اطلاعات سیستمی', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def message_type_badge(self, obj):
        colors = {
            'text': '#0d6efd',
            'file': '#fd7e14',
            'photo': '#198754',
            'link': '#6f42c1',
            'text_file': '#dc3545',
            'text_link': '#0dcaf0',
        }
        color = colors.get(obj.message_type, '#6c757d')
        return format_html(
            '<span style="background:{};color:white;padding:2px 8px;border-radius:10px">{}</span>',
            color, obj.get_message_type_display()
        )
    message_type_badge.short_description = 'نوع پیام'

    def is_active_badge(self, obj):
        if obj.is_active:
            return format_html('<span style="color:#198754;font-size:1.2em">✅ فعال</span>')
        return format_html('<span style="color:#dc3545;font-size:1.2em">❌ غیرفعال</span>')
    is_active_badge.short_description = 'وضعیت'

    def preview_section(self, obj):
        parts = []
        if obj.text_content:
            parts.append(f'<p><strong>متن:</strong><br>{obj.text_content[:200]}</p>')
        if obj.link_url:
            parts.append(f'<p><strong>لینک:</strong> <a href="{obj.link_url}" target="_blank">{obj.link_text or obj.link_url}</a></p>')
        if obj.file:
            parts.append(f'<p><strong>فایل:</strong> {obj.file.name}</p>')
        if obj.photo:
            parts.append(f'<p><strong>تصویر:</strong> <img src="{obj.photo.url}" style="max-height:150px"></p>')
        return mark_safe(''.join(parts) if parts else '<p>محتوایی برای پیش‌نمایش وجود ندارد</p>')
    preview_section.short_description = 'پیش‌نمایش'


# ─── BotUser ──────────────────────────────────────────────────────────────────

class RegistrationSessionInline(admin.StackedInline):
    model = RegistrationSession
    extra = 0
    readonly_fields = ('current_question_index', 'answers_display', 'is_completed', 'started_at', 'completed_at')
    fields = ('current_question_index', 'answers_display', 'is_completed', 'started_at', 'completed_at')
    can_delete = False

    def answers_display(self, obj):
        if not obj.answers:
            return 'بدون پاسخ'
        rows = ''.join(
            f'<tr><td style="padding:4px 12px;font-weight:bold">{k}</td>'
            f'<td style="padding:4px 12px">{v}</td></tr>'
            for k, v in obj.answers.items()
        )
        return mark_safe(
            f'<table style="border-collapse:collapse;width:100%">'
            f'<thead><tr><th style="padding:4px 12px;text-align:left">فیلد</th>'
            f'<th style="padding:4px 12px;text-align:left">پاسخ</th></tr></thead>'
            f'<tbody>{rows}</tbody></table>'
        )
    answers_display.short_description = 'پاسخ‌ها'


@admin.register(BotUser)
class BotUserAdmin(admin.ModelAdmin):
    list_display = (
        'full_name_display', 'bale_user_id', 'username_display',
        'is_registered_badge', 'is_blocked', 'first_seen', 'last_seen',
    )
    list_display_links = ('full_name_display', 'bale_user_id')
    list_filter = ('is_registered', 'is_blocked', 'first_seen')
    search_fields = ('first_name', 'last_name', 'username', 'bale_user_id')
    readonly_fields = ('bale_user_id', 'first_seen', 'last_seen', 'registered_at')
    ordering = ('-first_seen',)
    inlines = [RegistrationSessionInline]
    actions = ['mark_as_blocked', 'mark_as_unblocked']
    fieldsets = (
        ('اطلاعات بله', {
            'fields': ('bale_user_id', 'username', 'first_name', 'last_name'),
        }),
        ('وضعیت', {
            'fields': ('is_registered', 'is_blocked', 'registered_at'),
        }),
        ('یادداشت', {
            'fields': ('notes',),
        }),
        ('زمان‌بندی', {
            'fields': ('first_seen', 'last_seen'),
            'classes': ('collapse',),
        }),
    )

    def full_name_display(self, obj):
        return obj.full_name or f'User_{obj.bale_user_id}'
    full_name_display.short_description = 'نام کامل'

    def username_display(self, obj):
        if obj.username:
            return format_html('<code>@{}</code>', obj.username)
        return '—'
    username_display.short_description = 'نام کاربری'

    def is_registered_badge(self, obj):
        if obj.is_registered:
            return format_html('<span style="color:#198754;font-size:1.1em">✅</span>')
        return format_html('<span style="color:#dc3545;font-size:1.1em">⏳</span>')
    is_registered_badge.short_description = 'ثبت‌نام'
    is_registered_badge.admin_order_field = 'is_registered'

    @admin.action(description='بلاک کردن کاربران انتخابی')
    def mark_as_blocked(self, request, queryset):
        updated = queryset.update(is_blocked=True)
        self.message_user(request, f'{updated} کاربر بلاک شد.')

    @admin.action(description='رفع بلاک کاربران انتخابی')
    def mark_as_unblocked(self, request, queryset):
        updated = queryset.update(is_blocked=False)
        self.message_user(request, f'{updated} کاربر از بلاک خارج شد.')


# ─── RegistrationSession ──────────────────────────────────────────────────────

@admin.register(RegistrationSession)
class RegistrationSessionAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'current_question_index', 'is_completed_badge',
        'started_at', 'completed_at',
    )
    list_filter = ('is_completed', 'started_at')
    search_fields = ('user__first_name', 'user__last_name', 'user__username', 'user__bale_user_id')
    readonly_fields = ('user', 'started_at', 'completed_at', 'answers_table')
    ordering = ('-started_at',)
    fieldsets = (
        ('کاربر', {
            'fields': ('user',),
        }),
        ('وضعیت', {
            'fields': ('current_question_index', 'is_completed', 'started_at', 'completed_at'),
        }),
        ('پاسخ‌ها', {
            'fields': ('answers_table',),
        }),
        ('داده خام', {
            'fields': ('answers',),
            'classes': ('collapse',),
        }),
    )

    def is_completed_badge(self, obj):
        if obj.is_completed:
            return format_html('<span style="color:#198754;font-weight:bold">✅ تکمیل</span>')
        return format_html('<span style="color:#fd7e14;font-weight:bold">⏳ در حال انجام</span>')
    is_completed_badge.short_description = 'وضعیت'
    is_completed_badge.admin_order_field = 'is_completed'

    def answers_table(self, obj):
        if not obj.answers:
            return 'هیچ پاسخی ثبت نشده است'
        # Get question labels
        from .models import Question
        questions = {q.field_name: q.text for q in Question.objects.all()}
        rows = ''
        for field_name, answer in obj.answers.items():
            label = questions.get(field_name, field_name)
            rows += (
                f'<tr>'
                f'<td style="padding:6px 12px;border:1px solid #dee2e6;font-weight:bold">{label}</td>'
                f'<td style="padding:6px 12px;border:1px solid #dee2e6">{answer}</td>'
                f'</tr>'
            )
        return mark_safe(
            f'<table style="border-collapse:collapse;width:100%;margin-top:8px">'
            f'<thead><tr>'
            f'<th style="padding:6px 12px;border:1px solid #dee2e6;background:#f8f9fa">سوال</th>'
            f'<th style="padding:6px 12px;border:1px solid #dee2e6;background:#f8f9fa">پاسخ کاربر</th>'
            f'</tr></thead>'
            f'<tbody>{rows}</tbody></table>'
        )
    answers_table.short_description = 'جدول پاسخ‌ها'
