"""
Admin configuration for the registration app.
"""
import csv
from django.contrib import admin
from django.contrib import messages as django_messages
from django.http import HttpResponse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils import timezone

from .models import Question, FinalMessage, BotUser, RegistrationSession, WelcomeMessage, ScheduledMessage


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
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('محتوا', {
            'fields': ('order', 'text', 'field_name', 'question_type', 'choices'),
        }),
        ('اعتبارسنجی و تنظیمات', {
            'fields': ('validation_hint', 'is_required', 'is_active'),
        }),
        ('اطلاعات سیستمی', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def order_badge(self, obj):
        return format_html(
            '<span style="background:#0d6efd;color:#fff;padding:2px 10px;'
            'border-radius:12px;font-weight:bold;font-size:0.9em">{}</span>',
            obj.order,
        )
    order_badge.short_description = 'ترتیب'
    order_badge.admin_order_field = 'order'

    def text_preview(self, obj):
        return obj.text[:80] + '…' if len(obj.text) > 80 else obj.text
    text_preview.short_description = 'متن سوال'

    def question_type_badge(self, obj):
        colors = {
            'text':   '#6c757d',
            'phone':  '#198754',
            'email':  '#0dcaf0',
            'number': '#fd7e14',
            'choice': '#6f42c1',
        }
        color = colors.get(obj.question_type, '#6c757d')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 10px;'
            'border-radius:12px;font-size:0.85em">{}</span>',
            color, obj.get_question_type_display(),
        )
    question_type_badge.short_description = 'نوع'


# ─── WelcomeMessage ───────────────────────────────────────────────────────────

@admin.register(WelcomeMessage)
class WelcomeMessageAdmin(admin.ModelAdmin):
    list_display = ('title', 'is_active_badge', 'updated_at')
    list_display_links = ('title',)
    list_filter = ('is_active',)
    search_fields = ('title', 'text')
    readonly_fields = ('created_at', 'updated_at', 'text_preview')
    fieldsets = (
        ('اطلاعات اصلی', {
            'fields': ('title', 'is_active'),
        }),
        ('محتوا', {
            'fields': ('text', 'text_preview'),
        }),
        ('اطلاعات سیستمی', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def is_active_badge(self, obj):
        color = '#198754' if obj.is_active else '#6c757d'
        text = '✅ فعال' if obj.is_active else '❌ غیرفعال'
        return format_html('<span style="color:{}">{}</span>', color, text)
    is_active_badge.short_description = 'وضعیت'

    def text_preview(self, obj):
        return format_html('<div style="background:#f8f9fa;padding:8px 12px;border-radius:6px;border-left:3px solid #0d6efd">{}</div>', obj.text[:500])
    text_preview.short_description = 'پیش‌نمایش'

# ─── FinalMessage ─────────────────────────────────────────────────────────────

@admin.register(FinalMessage)
class FinalMessageAdmin(admin.ModelAdmin):
    list_display = ('order_badge', 'title', 'message_type_badge', 'is_active_badge', 'updated_at')
    list_display_links = ('title',)
    list_editable = ('is_active',)
    list_filter = ('message_type', 'is_active')
    search_fields = ('title', 'text_content')
    readonly_fields = ('created_at', 'updated_at', 'content_preview')
    fieldsets = (
        ('اطلاعات اصلی', {
            'fields': ('order', 'title', 'message_type', 'is_active'),
        }),
        ('محتوا', {
            'fields': ('text_content', 'file', 'photo', 'link_url', 'link_text'),
            'description': 'بسته به نوع پیام فیلدهای مربوطه را پر کنید.',
        }),
        ('پیش‌نمایش', {
            'fields': ('content_preview',),
        }),
        ('اطلاعات سیستمی', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def order_badge(self, obj):
        return format_html(
            '<span style="background:#0d6efd;color:#fff;padding:2px 10px;'
            'border-radius:12px;font-weight:bold;font-size:0.9em">{}</span>',
            obj.order,
        )
    order_badge.short_description = 'ترتیب'
    order_badge.admin_order_field = 'order'

    def is_active_badge(self, obj):
        color = '#198754' if obj.is_active else '#6c757d'
        text = '✅' if obj.is_active else '❌'
        return format_html('<span style="color:{}">{}</span>', color, text)
    is_active_badge.short_description = 'فعال'

    def message_type_badge(self, obj):
        colors = {
            'text':      '#0d6efd',
            'file':      '#fd7e14',
            'photo':     '#198754',
            'link':      '#6f42c1',
            'text_file': '#dc3545',
            'text_link': '#0dcaf0',
        }
        color = colors.get(obj.message_type, '#6c757d')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 10px;'
            'border-radius:12px;font-size:0.85em">{}</span>',
            color, obj.get_message_type_display(),
        )
    message_type_badge.short_description = 'نوع پیام'

    def content_preview(self, obj):
        parts = []
        if obj.text_content:
            parts.append(
                f'<div style="background:#f8f9fa;padding:8px 12px;border-radius:6px;'
                f'border-left:3px solid #0d6efd;margin-bottom:8px">'
                f'<strong>متن:</strong><br>{obj.text_content[:300]}</div>'
            )
        if obj.link_url:
            parts.append(
                f'<p><strong>لینک:</strong> '
                f'<a href="{obj.link_url}" target="_blank">{obj.link_text or obj.link_url}</a></p>'
            )
        if obj.file:
            parts.append(f'<p>📎 <strong>فایل:</strong> {obj.file.name.split("/")[-1]}</p>')
        if obj.photo:
            parts.append(
                f'<p><img src="{obj.photo.url}" '
                f'style="max-height:120px;border-radius:6px;border:1px solid #dee2e6"></p>'
            )
        return mark_safe(''.join(parts) or '<p style="color:#6c757d">محتوایی تنظیم نشده</p>')
    content_preview.short_description = 'پیش‌نمایش'


# ─── ScheduledMessage ─────────────────────────────────────────────────────────

@admin.register(ScheduledMessage)
class ScheduledMessageAdmin(admin.ModelAdmin):
    list_display = ('title', 'message_type_badge', 'scheduled_time', 'status_badge', 'sent_at')
    list_display_links = ('title',)
    list_filter = ('message_type', 'is_sent', 'scheduled_time')
    search_fields = ('title', 'text_content')
    readonly_fields = ('is_sent', 'sent_at', 'created_at', 'content_preview')
    date_hierarchy = 'scheduled_time'
    fieldsets = (
        ('اطلاعات اصلی', {
            'fields': ('title', 'message_type', 'scheduled_time'),
        }),
        ('محتوا', {
            'fields': ('text_content', 'file', 'photo', 'link_url', 'link_text'),
            'description': 'بسته به نوع پیام فیلدهای مربوطه را پر کنید.',
        }),
        ('پیش‌نمایش', {
            'fields': ('content_preview',),
        }),
        ('وضعیت ارسال', {
            'fields': ('is_sent', 'sent_at'),
            'classes': ('collapse',),
        }),
        ('اطلاعات سیستمی', {
            'fields': ('created_at',),
            'classes': ('collapse',),
        }),
    )
    
    actions = ['send_now']

    def message_type_badge(self, obj):
        colors = {
            'text':  '#0d6efd',
            'file':  '#fd7e14',
            'photo': '#198754',
            'link':  '#6f42c1',
        }
        color = colors.get(obj.message_type, '#6c757d')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 10px;'
            'border-radius:12px;font-size:0.85em">{}</span>',
            color, obj.get_message_type_display(),
        )
    message_type_badge.short_description = 'نوع پیام'

    def status_badge(self, obj):
        if obj.is_sent:
            return format_html(
                '<span style="background:#198754;color:#fff;padding:2px 10px;'
                'border-radius:12px;font-size:0.85em">✅ ارسال شده</span>'
            )
        elif obj.scheduled_time <= timezone.now():
            return format_html(
                '<span style="background:#dc3545;color:#fff;padding:2px 10px;'
                'border-radius:12px;font-size:0.85em">⏰ در حال ارسال...</span>'
            )
        else:
            return format_html(
                '<span style="background:#ffc107;color:#000;padding:2px 10px;'
                'border-radius:12px;font-size:0.85em">⏳ در انتظار</span>'
            )
    status_badge.short_description = 'وضعیت'

    def content_preview(self, obj):
        parts = []
        if obj.text_content:
            parts.append(
                f'<div style="background:#f8f9fa;padding:8px 12px;border-radius:6px;'
                f'border-left:3px solid #0d6efd;margin-bottom:8px">'
                f'<strong>متن:</strong><br>{obj.text_content[:300]}</div>'
            )
        if obj.link_url:
            parts.append(f'<p><strong>لینک:</strong> <a href="{obj.link_url}" target="_blank">{obj.link_text or obj.link_url}</a></p>')
        if obj.file:
            parts.append(f'<p>📎 <strong>فایل:</strong> {obj.file.name.split("/")[-1]}</p>')
        if obj.photo:
            parts.append(f'<p><img src="{obj.photo.url}" style="max-height:120px;border-radius:6px;border:1px solid #dee2e6"></p>')
        return mark_safe(''.join(parts) or '<p style="color:#6c757d">محتوایی تنظیم نشده</p>')
    content_preview.short_description = 'پیش‌نمایش'

    def send_now(self, request, queryset):
        """Admin action to send selected messages immediately."""
        from apps.registration.tasks import send_scheduled_messages
        
        # Update scheduled_time to now for selected messages
        count = queryset.filter(is_sent=False).update(scheduled_time=timezone.now())
        
        if count > 0:
            # Trigger the Celery task
            send_scheduled_messages.delay()
            self.message_user(
                request,
                f'{count} پیام برای ارسال فوری آماده شد. ارسال در حال انجام است...',
                level=django_messages.SUCCESS
            )
        else:
            self.message_user(
                request,
                'هیچ پیام ارسال نشده‌ای برای ارسال فوری وجود ندارد.',
                level=django_messages.WARNING
            )
    send_now.short_description = '📤 ارسال فوری پیام‌های انتخاب شده'


# ─── BotUser ──────────────────────────────────────────────────────────────────

class RegistrationSessionInline(admin.StackedInline):
    model = RegistrationSession
    extra = 0
    readonly_fields = (
        'current_question_index', 'answers_table',
        'is_completed', 'started_at', 'completed_at',
    )
    fields = (
        'current_question_index', 'answers_table',
        'is_completed', 'started_at', 'completed_at',
    )
    can_delete = False

    def answers_table(self, obj):
        if not obj or not obj.answers:
            return '—'
        questions = {q.field_name: q.text for q in Question.objects.all()}
        rows = ''.join(
            f'<tr>'
            f'<td style="padding:5px 10px;border:1px solid #dee2e6;font-weight:600;'
            f'background:#f8f9fa;width:40%">{questions.get(k, k)}</td>'
            f'<td style="padding:5px 10px;border:1px solid #dee2e6">{v}</td>'
            f'</tr>'
            for k, v in obj.answers.items()
        )
        return mark_safe(
            f'<table style="border-collapse:collapse;width:100%;font-size:0.9em">'
            f'<thead><tr>'
            f'<th style="padding:5px 10px;border:1px solid #dee2e6;background:#e9ecef">سوال</th>'
            f'<th style="padding:5px 10px;border:1px solid #dee2e6;background:#e9ecef">پاسخ</th>'
            f'</tr></thead><tbody>{rows}</tbody></table>'
        )
    answers_table.short_description = 'پاسخ‌ها'


def _export_users_csv(queryset):
    questions = list(Question.objects.filter(is_active=True).order_by('order'))
    field_names = [q.field_name for q in questions]
    q_labels = {q.field_name: q.text[:40] for q in questions}

    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    ts = timezone.now().strftime('%Y%m%d_%H%M%S')
    response['Content-Disposition'] = f'attachment; filename="registrations_{ts}.csv"'
    response.write('\ufeff')  # BOM for Excel

    writer = csv.writer(response)
    writer.writerow(
        ['شناسه بله', 'نام کاربری', 'نام', 'نام خانوادگی',
         'ثبت‌نام شده', 'زمان ثبت‌نام', 'اولین بازدید']
        + [q_labels.get(f, f) for f in field_names]
    )
    for user in queryset.iterator():
        answers = {}
        try:
            if hasattr(user, 'session') and user.session and user.session.answers:
                answers = user.session.answers
        except Exception:
            pass
        writer.writerow(
            [
                user.bale_user_id,
                user.username,
                user.first_name,
                user.last_name,
                '✓' if user.is_registered else '—',
                user.registered_at.strftime('%Y-%m-%d %H:%M') if user.registered_at else '—',
                user.first_seen.strftime('%Y-%m-%d %H:%M'),
            ]
            + [answers.get(f, '—') for f in field_names]
        )
    return response


@admin.register(BotUser)
class BotUserAdmin(admin.ModelAdmin):
    list_display = (
        'full_name_display', 'bale_user_id', 'username_display',
        'is_blocked', 'first_seen', 'last_seen',
    )
    list_display_links = ('full_name_display', 'bale_user_id')
    list_filter = ('is_registered', 'is_blocked', 'first_seen')
    search_fields = ('first_name', 'last_name', 'username', 'bale_user_id')
    readonly_fields = ('bale_user_id', 'first_seen', 'last_seen', 'registered_at')
    ordering = ('-first_seen',)
    inlines = [RegistrationSessionInline]
    actions = ['export_csv', 'mark_as_blocked', 'mark_as_unblocked', 'reset_registrations']

    # ── Stats for changelist template ──────────────────────────────────────────
    def changelist_view(self, request, extra_context=None):
        from django.utils import timezone as tz
        today = tz.localdate()
        total     = BotUser.objects.count()
        registered = BotUser.objects.filter(is_registered=True).count()
        blocked   = BotUser.objects.filter(is_blocked=True).count()
        in_progress = (
            RegistrationSession.objects.filter(is_completed=False).count()
        )
        today_count = BotUser.objects.filter(
            registered_at__date=today, is_registered=True
        ).count()
        completion_rate = round(registered / total * 100) if total else None
        extra_context = extra_context or {}
        extra_context['stats'] = {
            'total': total,
            'registered': registered,
            'blocked': blocked,
            'in_progress': in_progress,
            'today': today_count,
            'completion_rate': completion_rate,
        }
        return super().changelist_view(request, extra_context=extra_context)
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
        name = obj.full_name or f'User_{obj.bale_user_id}'
        return format_html('<strong>{}</strong>', name)
    full_name_display.short_description = 'نام کامل'
    full_name_display.admin_order_field = 'first_name'

    def username_display(self, obj):
        if obj.username:
            return format_html('<code style="font-size:0.9em">@{}</code>', obj.username)
        return format_html('<span style="color:#adb5bd">—</span>')
    username_display.short_description = 'نام کاربری'

    # ── Custom URL: export ALL users ──────────────────────────────────────────
    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        return [
            path(
                'export-all-csv/',
                self.admin_site.admin_view(self.export_all_csv),
                name='registration_botuser_export_all_csv',
            ),
        ] + urls

    def export_all_csv(self, request):
        return _export_users_csv(BotUser.objects.select_related('session').order_by('-registered_at'))

    # ── Actions ───────────────────────────────────────────────────────────────
    @admin.action(description='📥 خروجی CSV (کاربران انتخابی)')
    def export_csv(self, request, queryset):
        return _export_users_csv(queryset.select_related('session'))

    @admin.action(description='⛔ بلاک کردن کاربران انتخابی')
    def mark_as_blocked(self, request, queryset):
        n = queryset.update(is_blocked=True)
        self.message_user(request, f'{n} کاربر بلاک شد.', django_messages.WARNING)

    @admin.action(description='✅ رفع بلاک کاربران انتخابی')
    def mark_as_unblocked(self, request, queryset):
        n = queryset.update(is_blocked=False)
        self.message_user(request, f'{n} کاربر از بلاک خارج شد.', django_messages.SUCCESS)

    @admin.action(description='🔄 ریست ثبت‌نام (شروع مجدد)')
    def reset_registrations(self, request, queryset):
        user_ids = list(queryset.values_list('pk', flat=True))
        deleted, _ = RegistrationSession.objects.filter(user_id__in=user_ids).delete()
        queryset.update(is_registered=False, registered_at=None)
        self.message_user(
            request,
            f'ثبت‌نام {len(user_ids)} کاربر ریست شد ({deleted} جلسه حذف شد).',
            django_messages.WARNING,
        )


# ─── RegistrationSession ──────────────────────────────────────────────────────

@admin.register(RegistrationSession)
class RegistrationSessionAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'progress_display',
        'started_at', 'completed_at',
    )
    list_filter = ('is_completed', 'started_at')
    search_fields = (
        'user__first_name', 'user__last_name',
        'user__username', 'user__bale_user_id',
    )
    readonly_fields = ('user', 'started_at', 'completed_at', 'answers_table')
    ordering = ('-started_at',)
    fieldsets = (
        ('کاربر', {'fields': ('user',)}),
        ('وضعیت', {
            'fields': ('current_question_index', 'is_completed', 'started_at', 'completed_at'),
        }),
        ('پاسخ‌ها', {'fields': ('answers_table',)}),
        ('داده خام', {'fields': ('answers',), 'classes': ('collapse',)}),
    )

    def progress_display(self, obj):
        total = Question.objects.filter(is_active=True).count()
        answered = min(obj.current_question_index, total)
        if total == 0:
            return '—'
        pct = int(answered / total * 100)
        color = '#198754' if obj.is_completed else '#0d6efd'
        return mark_safe(
            f'<div style="display:flex;align-items:center;gap:8px">'
            f'<div style="background:#e9ecef;border-radius:8px;height:12px;'
            f'width:100px;overflow:hidden">'
            f'<div style="background:{color};height:100%;width:{pct}%"></div></div>'
            f'<small style="color:{color}">{answered}/{total}</small></div>'
        )
    progress_display.short_description = 'پیشرفت'

    def answers_table(self, obj):
        if not obj.answers:
            return mark_safe('<p style="color:#6c757d">هیچ پاسخی ثبت نشده است.</p>')
        questions = {q.field_name: q.text for q in Question.objects.all()}
        rows = ''.join(
            f'<tr>'
            f'<td style="padding:7px 12px;border:1px solid #dee2e6;background:#f8f9fa;'
            f'font-weight:600;width:40%">{questions.get(k, k)}</td>'
            f'<td style="padding:7px 12px;border:1px solid #dee2e6">{v}</td>'
            f'</tr>'
            for k, v in obj.answers.items()
        )
        return mark_safe(
            f'<table style="border-collapse:collapse;width:100%;margin-top:6px">'
            f'<thead><tr>'
            f'<th style="padding:7px 12px;border:1px solid #dee2e6;background:#e9ecef">سوال</th>'
            f'<th style="padding:7px 12px;border:1px solid #dee2e6;background:#e9ecef">پاسخ کاربر</th>'
            f'</tr></thead><tbody>{rows}</tbody></table>'
        )
    answers_table.short_description = 'جدول پاسخ‌ها'
