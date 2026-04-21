"""
Celery tasks for the registration app.
"""
import logging
import os
from celery import shared_task
from django.utils import timezone
from django.conf import settings
import telebot

logger = logging.getLogger(__name__)


@shared_task(name='apps.registration.send_scheduled_messages')
def send_scheduled_messages():
    """
    Send all pending scheduled messages to registered users.
    This task is triggered by Celery Beat based on the schedule.
    """
    from apps.registration.models import ScheduledMessage, BotUser
    
    now = timezone.now()
    
    # Get all pending scheduled messages that should be sent
    pending_messages = ScheduledMessage.objects.filter(
        is_sent=False,
        scheduled_time__lte=now
    ).order_by('scheduled_time')
    
    if not pending_messages.exists():
        logger.info('No scheduled messages to send')
        return {'status': 'success', 'message': 'No scheduled messages to send'}
    
    # Initialize bot
    bot_token = settings.BALE_BOT_TOKEN
    if not bot_token:
        logger.error('BALE_BOT_TOKEN not found in settings')
        return {'status': 'error', 'message': 'BALE_BOT_TOKEN not configured'}
    
    bot = telebot.TeleBot(bot_token)
    
    # Get all registered users
    registered_users = BotUser.objects.filter(
        is_registered=True,
        is_blocked=False
    )
    
    if not registered_users.exists():
        logger.warning('No registered users found')
        return {'status': 'warning', 'message': 'No registered users found'}
    
    results = []
    
    for scheduled_msg in pending_messages:
        logger.info(f'Sending scheduled message: {scheduled_msg.title}')
        
        success_count = 0
        fail_count = 0
        
        for user in registered_users:
            try:
                _send_message_to_user(bot, user.bale_user_id, scheduled_msg)
                success_count += 1
            except Exception as e:
                logger.error(f'Failed to send message to user {user.bale_user_id}: {e}')
                fail_count += 1
        
        # Mark as sent
        scheduled_msg.is_sent = True
        scheduled_msg.sent_at = timezone.now()
        scheduled_msg.save()
        
        result = {
            'title': scheduled_msg.title,
            'success': success_count,
            'failed': fail_count,
            'total': success_count + fail_count
        }
        results.append(result)
        logger.info(f'Sent "{scheduled_msg.title}" to {success_count} users ({fail_count} failed)')
    
    return {
        'status': 'success',
        'messages_sent': len(results),
        'results': results
    }


def _send_message_to_user(bot, chat_id, scheduled_msg):
    """Send a scheduled message to a specific user."""
    from apps.registration.models import ScheduledMessage
    
    mt = scheduled_msg.message_type
    
    if mt == ScheduledMessage.MessageType.TEXT:
        bot.send_message(chat_id, scheduled_msg.text_content, parse_mode='Markdown')
    
    elif mt == ScheduledMessage.MessageType.FILE:
        if scheduled_msg.file:
            with open(scheduled_msg.file.path, 'rb') as f:
                caption = scheduled_msg.text_content or None
                bot.send_document(
                    chat_id, f,
                    caption=caption,
                    parse_mode='Markdown' if caption else None,
                    visible_file_name=os.path.basename(scheduled_msg.file.name)
                )
    
    elif mt == ScheduledMessage.MessageType.PHOTO:
        if scheduled_msg.photo:
            with open(scheduled_msg.photo.path, 'rb') as f:
                caption = scheduled_msg.text_content or None
                bot.send_photo(
                    chat_id, f,
                    caption=caption,
                    parse_mode='Markdown' if caption else None
                )
    
    elif mt == ScheduledMessage.MessageType.LINK:
        text = scheduled_msg.text_content or scheduled_msg.link_url
        if scheduled_msg.link_text and scheduled_msg.link_url:
            from telebot import types
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton(
                text=scheduled_msg.link_text,
                url=scheduled_msg.link_url
            ))
            bot.send_message(chat_id, text, reply_markup=markup, parse_mode='Markdown')
        else:
            bot.send_message(
                chat_id,
                f'{text}\n\n{scheduled_msg.link_url}',
                parse_mode='Markdown'
            )
