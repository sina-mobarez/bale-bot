"""
Shared pytest fixtures for the Bale Registration Bot test suite.
"""
import os
import django
import pytest

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-pytest-only')
os.environ.setdefault('DB_NAME', ':memory:')
os.environ.setdefault('BALE_BOT_TOKEN', 'test_token_50_chars_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx')


@pytest.fixture
def question_factory(db):
    """Factory for creating Question instances."""
    from apps.registration.models import Question

    counter = [0]

    def make(order=None, question_type='text', required=True, choices=None, **kwargs):
        counter[0] += 1
        order = order if order is not None else counter[0]
        defaults = dict(
            order=order,
            text=f'Test question {order}?',
            field_name=f'field_{order}',
            question_type=question_type,
            is_required=required,
            choices=choices or '',
            is_active=True,
        )
        defaults.update(kwargs)
        return Question.objects.create(**defaults)

    return make


@pytest.fixture
def final_message_factory(db):
    """Factory for creating FinalMessage instances."""
    from apps.registration.models import FinalMessage

    def make(message_type='text', text='ثبت‌نام کامل شد!', active=True, **kwargs):
        return FinalMessage.objects.create(
            title='Test Final Message',
            message_type=message_type,
            text_content=text,
            is_active=active,
            **kwargs,
        )

    return make


@pytest.fixture
def bot_user_factory(db):
    """Factory for creating BotUser instances."""
    from apps.registration.models import BotUser

    counter = [100000]

    def make(user_id=None, registered=False, blocked=False, **kwargs):
        counter[0] += 1
        uid = user_id or counter[0]
        return BotUser.objects.create(
            bale_user_id=uid,
            first_name=f'User{uid}',
            is_registered=registered,
            is_blocked=blocked,
            **kwargs,
        )

    return make


@pytest.fixture
def session_factory(db, bot_user_factory):
    """Factory for creating RegistrationSession instances."""
    from apps.registration.models import RegistrationSession

    def make(bot_user=None, index=0, answers=None, completed=False):
        if bot_user is None:
            bot_user = bot_user_factory()
        return RegistrationSession.objects.create(
            user=bot_user,
            current_question_index=index,
            answers=answers or {},
            is_completed=completed,
        )

    return make


@pytest.fixture
def mock_tg_user():
    """A fake telegram.types.User-like object."""
    from unittest.mock import MagicMock
    user = MagicMock()
    user.id = 999888777
    user.first_name = 'سینا'
    user.last_name = 'تستی'
    user.username = 'sina_test'
    return user


@pytest.fixture
def mock_bot():
    """A mocked telebot.TeleBot instance that records calls."""
    from unittest.mock import MagicMock, patch
    bot = MagicMock()
    bot.sent_messages = []

    def _record_send(chat_id, text, **kwargs):
        bot.sent_messages.append({'chat_id': chat_id, 'text': text, **kwargs})
        return MagicMock()

    bot.send_message.side_effect = _record_send
    return bot
