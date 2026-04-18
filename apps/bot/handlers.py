"""
Bale Bot — Registration handlers using telegram-bale-bot (pyTelegramBotAPI fork).

State machine is 100% DB-driven via RegistrationSession.current_question_index.
No ConversationHandler needed — one message handler reads state from DB each time.

Flow:
  /start  → create/resume session → ask Q1
  <text>  → validate → save → ask next Q (or send FinalMessage on last Q)
  /cancel → cancel in-progress session
  /restart → hard reset, start over
"""
import logging
import os
import re

import telebot
from telebot import types
from django.utils import timezone

logger = logging.getLogger(__name__)


# ─── Simple in-process rate limiter ─────────────────────────────────────────
# Limits each user to MAX_MESSAGES_PER_WINDOW messages per WINDOW_SECONDS.
# Uses a dict of deque — resets automatically on restart (fine for single process).

from collections import defaultdict, deque
import time

_RATE_WINDOW_SECONDS = 10
_RATE_MAX_MESSAGES   = 8
_user_timestamps: dict = defaultdict(deque)


def _is_rate_limited(user_id: int) -> bool:
    """Returns True if the user has exceeded the rate limit."""
    now = time.monotonic()
    dq = _user_timestamps[user_id]
    # Drop old timestamps outside the window
    while dq and now - dq[0] > _RATE_WINDOW_SECONDS:
        dq.popleft()
    if len(dq) >= _RATE_MAX_MESSAGES:
        return True
    dq.append(now)
    return False


# ─── DB helpers (plain sync — fine inside telebot handlers) ──────────────────

def _get_or_create_bot_user(tg_user):
    from apps.registration.models import BotUser
    user, created = BotUser.objects.get_or_create(
        bale_user_id=tg_user.id,
        defaults={
            'first_name': tg_user.first_name or '',
            'last_name': getattr(tg_user, 'last_name', '') or '',
            'username': getattr(tg_user, 'username', '') or '',
        },
    )
    if not created:
        changed = False
        for field, val in [
            ('first_name', tg_user.first_name or ''),
            ('last_name', getattr(tg_user, 'last_name', '') or ''),
            ('username', getattr(tg_user, 'username', '') or ''),
        ]:
            if getattr(user, field) != val:
                setattr(user, field, val)
                changed = True
        if changed:
            user.save(update_fields=['first_name', 'last_name', 'username'])
    return user


def _get_or_create_session(bot_user):
    from apps.registration.models import RegistrationSession
    session, _ = RegistrationSession.objects.get_or_create(
        user=bot_user,
        defaults={'current_question_index': 0, 'answers': {}},
    )
    return session


def _get_active_questions():
    from apps.registration.models import Question
    return list(Question.objects.filter(is_active=True).order_by('order'))


def _get_active_final_message():
    from apps.registration.models import FinalMessage
    return FinalMessage.objects.filter(is_active=True).first()


def _save_answer(session, field_name: str, answer: str, next_index: int):
    session.answers[field_name] = answer
    session.current_question_index = next_index
    session.save(update_fields=['answers', 'current_question_index'])


def _complete_session(session, bot_user):
    now = timezone.now()
    session.is_completed = True
    session.completed_at = now
    session.save(update_fields=['is_completed', 'completed_at'])
    bot_user.is_registered = True
    bot_user.registered_at = now
    bot_user.save(update_fields=['is_registered', 'registered_at'])


def _reset_session(bot_user):
    from apps.registration.models import RegistrationSession
    RegistrationSession.objects.filter(user=bot_user).delete()
    bot_user.is_registered = False
    bot_user.registered_at = None
    bot_user.save(update_fields=['is_registered', 'registered_at'])


# ─── Admin notification ──────────────────────────────────────────────────────

def _notify_admin(bot, bot_user, answers: dict):
    """
    If BALE_ADMIN_CHAT_ID is set in settings, send a notification message
    to the admin when a user completes registration.
    """
    from django.conf import settings as dj_settings
    admin_chat_id = getattr(dj_settings, 'BALE_ADMIN_CHAT_ID', None)
    if not admin_chat_id:
        return
    try:
        name = bot_user.full_name or f'User_{bot_user.bale_user_id}'
        username = f' (@{bot_user.username})' if bot_user.username else ''
        lines = [
            '\U0001f514 *\u062b\u0628\u062a\u200c\u0646\u0627\u0645 \u062c\u062f\u06cc\u062f*',
            f'\U0001f464 {name}{username}',
            f'\U0001f194 `{bot_user.bale_user_id}`',
            '',
        ]
        for k, v in answers.items():
            lines.append(f'\u2022 *{k}*: {v}')
        text = '\n'.join(lines)
        bot.send_message(admin_chat_id, text, parse_mode='Markdown')
    except Exception as e:
        logger.warning(f'Could not send admin notification: {e}')


# ─── Validators ───────────────────────────────────────────────────────────────

def validate_answer(question, text: str):
    """Returns (is_valid: bool, error_message: str)."""
    from apps.registration.models import Question

    text = text.strip()

    if question.is_required and not text:
        return False, '⚠️ این فیلد اجباری است. لطفاً پاسخ دهید.'

    # Optional field with empty answer — skip type-specific validation
    if not text:
        return True, ''

    qtype = question.question_type

    if qtype == Question.QuestionType.PHONE:
        cleaned = re.sub(r'[\s\-\(\)]', '', text)
        if not re.match(r'^(\+98|0098|0)?9\d{9}$', cleaned):
            return False, question.validation_hint or '⚠️ شماره موبایل معتبر نیست. مثال: 09123456789'
        return True, ''

    if qtype == Question.QuestionType.EMAIL:
        if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', text):
            return False, question.validation_hint or '⚠️ ایمیل معتبر نیست. مثال: name@example.com'
        return True, ''

    if qtype == Question.QuestionType.NUMBER:
        if not re.match(r'^\d+(\.\d+)?$', text):
            return False, question.validation_hint or '⚠️ لطفاً فقط عدد وارد کنید.'
        return True, ''

    if qtype == Question.QuestionType.CHOICE:
        choices = question.get_choices_list()
        if choices and text not in choices:
            return False, question.validation_hint or '⚠️ لطفاً یکی از گزینه‌های موجود را انتخاب کنید.'
        return True, ''

    return True, ''


# ─── Keyboard builders ────────────────────────────────────────────────────────

def make_choice_keyboard(question):
    choices = question.get_choices_list()
    if not choices:
        return None
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    for i in range(0, len(choices), 2):
        row = choices[i:i + 2]
        markup.add(*[types.KeyboardButton(c) for c in row])
    return markup


def remove_keyboard():
    return types.ReplyKeyboardRemove()


def make_inline_link(url: str, label: str):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(text=label or '🔗 باز کردن لینک', url=url))
    return markup


# ─── Send question ────────────────────────────────────────────────────────────

def send_question(bot: telebot.TeleBot, chat_id: int, question):
    from apps.registration.models import Question
    if question.question_type == Question.QuestionType.CHOICE:
        kb = make_choice_keyboard(question)
        bot.send_message(chat_id, question.text, reply_markup=kb)
    else:
        bot.send_message(chat_id, question.text, reply_markup=remove_keyboard())


# ─── Send final message ───────────────────────────────────────────────────────

def send_final_message(bot: telebot.TeleBot, chat_id: int, final_msg):
    from apps.registration.models import FinalMessage
    mt = final_msg.message_type

    try:
        if mt == FinalMessage.MessageType.TEXT:
            bot.send_message(chat_id, final_msg.text_content, parse_mode='Markdown')

        elif mt == FinalMessage.MessageType.FILE:
            with open(final_msg.file.path, 'rb') as f:
                caption = final_msg.text_content or None
                bot.send_document(chat_id, f,
                                  caption=caption,
                                  parse_mode='Markdown' if caption else None,
                                  visible_file_name=os.path.basename(final_msg.file.name))

        elif mt == FinalMessage.MessageType.PHOTO:
            with open(final_msg.photo.path, 'rb') as f:
                caption = final_msg.text_content or None
                bot.send_photo(chat_id, f,
                               caption=caption,
                               parse_mode='Markdown' if caption else None)

        elif mt == FinalMessage.MessageType.LINK:
            text = final_msg.text_content or final_msg.link_url
            if final_msg.link_text and final_msg.link_url:
                markup = make_inline_link(final_msg.link_url, final_msg.link_text)
                bot.send_message(chat_id, text, reply_markup=markup, parse_mode='Markdown')
            else:
                bot.send_message(chat_id, f'{text}\n\n{final_msg.link_url}', parse_mode='Markdown')

        elif mt == FinalMessage.MessageType.TEXT_AND_FILE:
            if final_msg.text_content:
                bot.send_message(chat_id, final_msg.text_content, parse_mode='Markdown')
            if final_msg.file:
                with open(final_msg.file.path, 'rb') as f:
                    bot.send_document(chat_id, f,
                                      visible_file_name=os.path.basename(final_msg.file.name))

        elif mt == FinalMessage.MessageType.TEXT_AND_LINK:
            text = final_msg.text_content or final_msg.link_url
            markup = None
            if final_msg.link_url and final_msg.link_text:
                markup = make_inline_link(final_msg.link_url, final_msg.link_text)
            bot.send_message(chat_id, text, reply_markup=markup, parse_mode='Markdown')

    except Exception as e:
        logger.error(f'Error sending final message to {chat_id}: {e}', exc_info=True)
        bot.send_message(chat_id, '✅ ثبت‌نام شما با موفقیت انجام شد!')


# ─── Register all handlers ────────────────────────────────────────────────────

def register_handlers(bot: telebot.TeleBot):
    """Attach all handlers to the bot instance. Called once from runbot.py."""

    @bot.message_handler(commands=['start'])
    def cmd_start(message: types.Message):
        tg_user = message.from_user
        chat_id = message.chat.id
        logger.info(f'User {tg_user.id} sent /start')

        bot_user = _get_or_create_bot_user(tg_user)
        if bot_user.is_blocked:
            bot.send_message(chat_id, '⛔ دسترسی شما به این ربات محدود شده است.',
                             reply_markup=remove_keyboard())
            return

        questions = _get_active_questions()
        if not questions:
            bot.send_message(chat_id,
                             '⚠️ در حال حاضر فرآیند ثبت‌نام فعال نیست.\n'
                             'لطفاً بعداً دوباره تلاش کنید.')
            return

        session = _get_or_create_session(bot_user)
        if session.is_completed:
            bot.send_message(chat_id,
                             '✅ ثبت‌نام شما قبلاً تکمیل شده است.\n\n'
                             'برای شروع مجدد /restart را ارسال کنید.',
                             reply_markup=remove_keyboard())
            return

        first_name = tg_user.first_name or 'کاربر'
        bot.send_message(
            chat_id,
            f'سلام {first_name}! 👋\n\n'
            f'به فرآیند ثبت‌نام خوش آمدید.\n'
            f'لطفاً به سوالات زیر پاسخ دهید.\n\n'
            f'برای لغو هر زمان /cancel را ارسال کنید.',
            reply_markup=remove_keyboard(),
        )
        idx = session.current_question_index
        send_question(bot, chat_id, questions[idx])

    @bot.message_handler(commands=['cancel'])
    def cmd_cancel(message: types.Message):
        bot.send_message(
            message.chat.id,
            '❌ فرآیند ثبت‌نام لغو شد.\n'
            'هر زمان با /start دوباره شروع کنید.',
            reply_markup=remove_keyboard(),
        )

    @bot.message_handler(commands=['restart'])
    def cmd_restart(message: types.Message):
        bot_user = _get_or_create_bot_user(message.from_user)
        _reset_session(bot_user)
        bot.send_message(
            message.chat.id,
            '🔄 جلسه ثبت‌نام ریست شد.\n/start را بزنید برای شروع مجدد.',
            reply_markup=remove_keyboard(),
        )

    @bot.message_handler(content_types=['text'])
    def handle_text(message: types.Message):
        tg_user = message.from_user
        chat_id = message.chat.id
        text = (message.text or '').strip()

        if _is_rate_limited(tg_user.id):
            bot.send_message(chat_id, '⏳ لطفاً کمی صبر کنید.')
            return

        bot_user = _get_or_create_bot_user(tg_user)
        if bot_user.is_blocked:
            bot.send_message(chat_id, '⛔ دسترسی شما به این ربات محدود شده است.')
            return

        questions = _get_active_questions()
        if not questions:
            bot.send_message(chat_id, '⚠️ در حال حاضر فرآیند ثبت‌نام فعال نیست.')
            return

        session = _get_or_create_session(bot_user)

        if session.is_completed:
            bot.send_message(
                chat_id,
                '✅ ثبت‌نام شما قبلاً کامل شده است.\n'
                'برای شروع مجدد /restart را ارسال کنید.',
                reply_markup=remove_keyboard(),
            )
            return

        idx = session.current_question_index
        if idx >= len(questions):
            _complete_session(session, bot_user)
            bot.send_message(chat_id, '✅ ثبت‌نام کامل شد!', reply_markup=remove_keyboard())
            return

        current_q = questions[idx]
        is_valid, error_msg = validate_answer(current_q, text)
        if not is_valid:
            bot.send_message(chat_id, error_msg)
            send_question(bot, chat_id, current_q)
            return

        next_idx = idx + 1
        _save_answer(session, current_q.field_name, text, next_idx)
        logger.info(f'User {tg_user.id} answered Q{idx + 1} ({current_q.field_name})')

        if next_idx >= len(questions):
            _complete_session(session, bot_user)
            logger.info(f'User {tg_user.id} completed registration')
            bot.send_message(
                chat_id,
                '🎉 ثبت‌نام شما با موفقیت انجام شد!\n\nدر حال آماده‌سازی اطلاعات...',
                reply_markup=remove_keyboard(),
            )
            final_msg = _get_active_final_message()
            if final_msg:
                send_final_message(bot, chat_id, final_msg)
            else:
                bot.send_message(chat_id, '✅ ثبت‌نام کامل شد. با تشکر!')

            # Notify admin (if BALE_ADMIN_CHAT_ID is configured)
            _notify_admin(bot, bot_user, session.answers)
            return

        send_question(bot, chat_id, questions[next_idx])

    @bot.message_handler(content_types=[
        'photo', 'video', 'audio', 'document', 'sticker',
        'voice', 'video_note', 'location', 'contact',
    ])
    def handle_non_text(message: types.Message):
        bot.send_message(
            message.chat.id,
            '⚠️ لطفاً فقط پیام متنی ارسال کنید.\n'
            'برای لغو /cancel را بزنید.',
        )
