"""
Bale Bot — Registration conversation handlers.

Flow:
  /start → greet → ask Q1 → Q2 → … → Qn → send FinalMessage → done

State machine (ConversationHandler):
  ANSWERING  : user is in the middle of the question flow
"""
import logging
import re
from asgiref.sync import sync_to_async
from django.utils import timezone

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    KeyboardButton,
)
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
)
from telegram.constants import ParseMode

logger = logging.getLogger(__name__)

# ─── Conversation states ──────────────────────────────────────────────────────
ANSWERING = 1

# ─── Helpers (sync → async DB wrappers) ──────────────────────────────────────

@sync_to_async
def _get_active_questions():
    from apps.registration.models import Question
    return list(Question.objects.filter(is_active=True).order_by('order'))


@sync_to_async
def _get_active_final_message():
    from apps.registration.models import FinalMessage
    return FinalMessage.objects.filter(is_active=True).first()


@sync_to_async
def _get_or_create_bot_user(tg_user):
    from apps.registration.models import BotUser
    user, created = BotUser.objects.get_or_create(
        bale_user_id=tg_user.id,
        defaults={
            'first_name': tg_user.first_name or '',
            'last_name': tg_user.last_name or '',
            'username': tg_user.username or '',
        },
    )
    if not created:
        # Update name/username in case they changed
        changed = False
        for field, val in [
            ('first_name', tg_user.first_name or ''),
            ('last_name', tg_user.last_name or ''),
            ('username', tg_user.username or ''),
        ]:
            if getattr(user, field) != val:
                setattr(user, field, val)
                changed = True
        if changed:
            user.save(update_fields=['first_name', 'last_name', 'username'])
    return user, created


@sync_to_async
def _get_or_create_session(bot_user):
    from apps.registration.models import RegistrationSession
    session, created = RegistrationSession.objects.get_or_create(
        user=bot_user,
        defaults={'current_question_index': 0, 'answers': {}},
    )
    return session, created


@sync_to_async
def _save_answer(session, field_name, answer, next_index):
    session.answers[field_name] = answer
    session.current_question_index = next_index
    session.save(update_fields=['answers', 'current_question_index'])


@sync_to_async
def _complete_session(session, bot_user):
    now = timezone.now()
    session.is_completed = True
    session.completed_at = now
    session.save(update_fields=['is_completed', 'completed_at'])

    bot_user.is_registered = True
    bot_user.registered_at = now
    bot_user.save(update_fields=['is_registered', 'registered_at'])


@sync_to_async
def _reset_session(bot_user):
    from apps.registration.models import RegistrationSession
    RegistrationSession.objects.filter(user=bot_user).delete()
    bot_user.is_registered = False
    bot_user.registered_at = None
    bot_user.save(update_fields=['is_registered', 'registered_at'])


@sync_to_async
def _is_blocked(bot_user):
    bot_user.refresh_from_db(fields=['is_blocked'])
    return bot_user.is_blocked


# ─── Validators ───────────────────────────────────────────────────────────────

def validate_answer(question, text: str) -> tuple[bool, str]:
    """
    Returns (is_valid, error_message).
    """
    from apps.registration.models import Question

    text = text.strip()

    if question.is_required and not text:
        return False, '⚠️ این فیلد اجباری است. لطفاً پاسخ دهید.'

    qtype = question.question_type

    if qtype == Question.QuestionType.PHONE:
        cleaned = re.sub(r'[\s\-\(\)]', '', text)
        if not re.match(r'^(\+98|0098|0)?9\d{9}$', cleaned):
            hint = question.validation_hint or '⚠️ شماره تلفن معتبر نیست. مثال: 09123456789'
            return False, hint
        return True, ''

    if qtype == Question.QuestionType.EMAIL:
        if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', text):
            hint = question.validation_hint or '⚠️ ایمیل معتبر نیست. مثال: name@example.com'
            return False, hint
        return True, ''

    if qtype == Question.QuestionType.NUMBER:
        if not re.match(r'^\d+(\.\d+)?$', text):
            hint = question.validation_hint or '⚠️ لطفاً فقط عدد وارد کنید.'
            return False, hint
        return True, ''

    if qtype == Question.QuestionType.CHOICE:
        choices = question.get_choices_list()
        if choices and text not in choices:
            hint = question.validation_hint or f'⚠️ لطفاً یکی از گزینه‌های موجود را انتخاب کنید.'
            return False, hint
        return True, ''

    return True, ''


# ─── Keyboard builders ────────────────────────────────────────────────────────

def build_choices_keyboard(question):
    """Build a ReplyKeyboardMarkup from question choices."""
    choices = question.get_choices_list()
    if not choices:
        return None
    # Arrange in rows of 2
    rows = []
    for i in range(0, len(choices), 2):
        rows.append([KeyboardButton(c) for c in choices[i:i+2]])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True, one_time_keyboard=True)


def build_inline_link_keyboard(url: str, text: str):
    """Build an inline keyboard with a URL button."""
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(text=text or '🔗 باز کردن لینک', url=url)
    ]])


# ─── Ask a specific question ──────────────────────────────────────────────────

async def ask_question(update_or_message, question):
    """Send a question to the user with appropriate keyboard."""
    from apps.registration.models import Question

    keyboard = None
    if question.question_type == Question.QuestionType.CHOICE:
        keyboard = build_choices_keyboard(question)

    if keyboard:
        await update_or_message.reply_text(
            question.text,
            reply_markup=keyboard,
        )
    else:
        await update_or_message.reply_text(
            question.text,
            reply_markup=ReplyKeyboardRemove(),
        )


# ─── Send final message ───────────────────────────────────────────────────────

async def send_final_message(message, final_msg, context: ContextTypes.DEFAULT_TYPE):
    """
    Send the configured FinalMessage to the user.
    Supports: text, file, photo, link, text+file, text+link
    """
    from apps.registration.models import FinalMessage

    chat_id = message.chat_id
    mt = final_msg.message_type

    try:
        if mt == FinalMessage.MessageType.TEXT:
            await context.bot.send_message(
                chat_id=chat_id,
                text=final_msg.text_content,
                parse_mode=ParseMode.MARKDOWN,
            )

        elif mt == FinalMessage.MessageType.FILE:
            caption = final_msg.text_content or None
            with open(final_msg.file.path, 'rb') as f:
                await context.bot.send_document(
                    chat_id=chat_id,
                    document=f,
                    filename=final_msg.file.name.split('/')[-1],
                    caption=caption,
                    parse_mode=ParseMode.MARKDOWN if caption else None,
                )

        elif mt == FinalMessage.MessageType.PHOTO:
            caption = final_msg.text_content or None
            with open(final_msg.photo.path, 'rb') as f:
                await context.bot.send_photo(
                    chat_id=chat_id,
                    photo=f,
                    caption=caption,
                    parse_mode=ParseMode.MARKDOWN if caption else None,
                )

        elif mt == FinalMessage.MessageType.LINK:
            text = final_msg.text_content or final_msg.link_url
            if final_msg.link_text:
                keyboard = build_inline_link_keyboard(final_msg.link_url, final_msg.link_text)
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    reply_markup=keyboard,
                    parse_mode=ParseMode.MARKDOWN,
                )
            else:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f'{text}\n\n{final_msg.link_url}',
                    parse_mode=ParseMode.MARKDOWN,
                )

        elif mt == FinalMessage.MessageType.TEXT_AND_FILE:
            if final_msg.text_content:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=final_msg.text_content,
                    parse_mode=ParseMode.MARKDOWN,
                )
            if final_msg.file:
                with open(final_msg.file.path, 'rb') as f:
                    await context.bot.send_document(
                        chat_id=chat_id,
                        document=f,
                        filename=final_msg.file.name.split('/')[-1],
                    )

        elif mt == FinalMessage.MessageType.TEXT_AND_LINK:
            keyboard = None
            if final_msg.link_url and final_msg.link_text:
                keyboard = build_inline_link_keyboard(final_msg.link_url, final_msg.link_text)
            await context.bot.send_message(
                chat_id=chat_id,
                text=final_msg.text_content or final_msg.link_url,
                reply_markup=keyboard,
                parse_mode=ParseMode.MARKDOWN,
            )

    except Exception as e:
        logger.error(f'Error sending final message to {chat_id}: {e}', exc_info=True)
        await context.bot.send_message(
            chat_id=chat_id,
            text='✅ ثبت‌نام شما با موفقیت انجام شد!',
        )


# ─── Conversation handlers ────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry point: /start"""
    tg_user = update.effective_user
    message = update.effective_message

    logger.info(f'User {tg_user.id} ({tg_user.username}) started the bot')

    # Get/create bot user
    bot_user, _ = await _get_or_create_bot_user(tg_user)

    # Block check
    if await _is_blocked(bot_user):
        await message.reply_text(
            '⛔ دسترسی شما به این ربات محدود شده است.',
            reply_markup=ReplyKeyboardRemove(),
        )
        return ConversationHandler.END

    # Already registered
    if bot_user.is_registered:
        await message.reply_text(
            '✅ شما قبلاً ثبت‌نام کرده‌اید.\n\n'
            'برای شروع مجدد /restart را ارسال کنید.',
            reply_markup=ReplyKeyboardRemove(),
        )
        return ConversationHandler.END

    # Load active questions
    questions = await _get_active_questions()
    if not questions:
        await message.reply_text(
            '⚠️ در حال حاضر فرآیند ثبت‌نام فعال نیست.\n'
            'لطفاً بعداً دوباره تلاش کنید.',
        )
        return ConversationHandler.END

    # Get/create session
    session, _ = await _get_or_create_session(bot_user)

    if session.is_completed:
        await message.reply_text(
            '✅ ثبت‌نام شما قبلاً تکمیل شده است.',
            reply_markup=ReplyKeyboardRemove(),
        )
        return ConversationHandler.END

    # Store state in context
    context.user_data['bot_user_id'] = bot_user.pk
    context.user_data['question_ids'] = [q.pk for q in questions]

    # Welcome message
    first_name = tg_user.first_name or 'کاربر'
    await message.reply_text(
        f'سلام {first_name}! 👋\n\n'
        f'به فرآیند ثبت‌نام خوش آمدید.\n'
        f'لطفاً به سوالات زیر پاسخ دهید.\n\n'
        f'برای لغو هر زمان /cancel را ارسال کنید.',
        reply_markup=ReplyKeyboardRemove(),
    )

    # Ask the first unanswered question
    idx = session.current_question_index
    if idx >= len(questions):
        idx = 0
    await ask_question(message, questions[idx])
    return ANSWERING


async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user's text answer during the registration flow."""
    tg_user = update.effective_user
    message = update.effective_message
    text = message.text.strip() if message.text else ''

    # Load questions
    questions = await _get_active_questions()
    if not questions:
        await message.reply_text('⚠️ فرآیند ثبت‌نام دیگر فعال نیست.')
        return ConversationHandler.END

    # Get session
    bot_user, _ = await _get_or_create_bot_user(tg_user)
    session, _ = await _get_or_create_session(bot_user)
    idx = session.current_question_index

    if idx >= len(questions):
        await message.reply_text('✅ ثبت‌نام شما تکمیل شده است.')
        return ConversationHandler.END

    current_q = questions[idx]

    # Validate
    is_valid, error_msg = validate_answer(current_q, text)
    if not is_valid:
        await message.reply_text(error_msg)
        # Re-ask the same question
        await ask_question(message, current_q)
        return ANSWERING

    # Save answer and advance
    next_idx = idx + 1
    await _save_answer(session, current_q.field_name, text.strip(), next_idx)
    logger.info(f'User {tg_user.id} answered Q{idx+1}: {current_q.field_name}={text[:50]}')

    # Check if this was the last question
    if next_idx >= len(questions):
        # Mark as completed
        await _complete_session(session, bot_user)
        logger.info(f'User {tg_user.id} completed registration')

        # Send success message
        await message.reply_text(
            '🎉 ثبت‌نام شما با موفقیت انجام شد!\n\n'
            'در حال آماده‌سازی اطلاعات...',
            reply_markup=ReplyKeyboardRemove(),
        )

        # Send final message
        final_msg = await _get_active_final_message()
        if final_msg:
            await send_final_message(message, final_msg, context)
        else:
            await message.reply_text('✅ ثبت‌نام کامل شد. با تشکر!')

        return ConversationHandler.END

    # Ask next question
    await ask_question(message, questions[next_idx])
    return ANSWERING


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel the registration process."""
    await update.effective_message.reply_text(
        '❌ فرآیند ثبت‌نام لغو شد.\n'
        'هر زمان که خواستید با /start دوباره شروع کنید.',
        reply_markup=ReplyKeyboardRemove(),
    )
    context.user_data.clear()
    return ConversationHandler.END


async def cmd_restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Allow a user to restart registration (admin use or testing)."""
    tg_user = update.effective_user
    bot_user, _ = await _get_or_create_bot_user(tg_user)
    await _reset_session(bot_user)
    context.user_data.clear()
    await update.effective_message.reply_text(
        '🔄 جلسه ثبت‌نام ریست شد.\n/start را بزنید برای شروع مجدد.',
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END


async def handle_unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle unexpected message types (photo, sticker, etc.) during registration."""
    await update.effective_message.reply_text(
        '⚠️ لطفاً فقط متن ارسال کنید.\n'
        'برای لغو /cancel را بزنید.'
    )
    return ANSWERING


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Global error handler."""
    logger.error(f'Exception while handling update: {context.error}', exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        await update.effective_message.reply_text(
            '⚠️ خطایی رخ داد. لطفاً دوباره تلاش کنید یا /start را بزنید.'
        )
