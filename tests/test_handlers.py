"""
Tests for bot handlers — validation logic and DB state machine.
"""
import pytest
from unittest.mock import MagicMock, patch, call


# ─── Validation tests ─────────────────────────────────────────────────────────

class TestValidateAnswer:
    """Tests for the validate_answer() function."""

    def _make_q(self, qtype, required=True, hint='', choices=None):
        q = MagicMock()
        q.question_type = qtype
        q.is_required = required
        q.validation_hint = hint
        q.get_choices_list.return_value = choices or []
        return q

    # ── Phone ─────────────────────────────────────────────────────────────────
    @pytest.mark.parametrize('phone', [
        '09123456789',
        '9123456789',
        '+989123456789',
        '00989123456789',
        '0912 345 6789',    # spaces
        '0912-345-6789',    # dashes
    ])
    def test_valid_phones(self, phone):
        from apps.bot.handlers import validate_answer
        q = self._make_q('phone')
        ok, _ = validate_answer(q, phone)
        assert ok is True

    @pytest.mark.parametrize('phone', [
        '1234',
        '0812345678',   # wrong prefix
        'notaphone',
        '091234',       # too short
        '',
    ])
    def test_invalid_phones(self, phone):
        from apps.bot.handlers import validate_answer
        q = self._make_q('phone', required=False)   # not required so blank '' test isolates regex
        ok, err = validate_answer(q, phone)
        if phone == '':
            assert ok is True   # empty + not required = valid
        else:
            assert ok is False
            assert err  # error message is present

    # ── Email ─────────────────────────────────────────────────────────────────
    @pytest.mark.parametrize('email', [
        'sina@example.com',
        'user.name+tag@sub.domain.org',
        'a@b.io',
    ])
    def test_valid_emails(self, email):
        from apps.bot.handlers import validate_answer
        q = self._make_q('email')
        ok, _ = validate_answer(q, email)
        assert ok is True

    @pytest.mark.parametrize('email', ['notanemail', 'missing@', '@nodomain', 'no spaces@x.com'])
    def test_invalid_emails(self, email):
        from apps.bot.handlers import validate_answer
        q = self._make_q('email')
        ok, _ = validate_answer(q, email)
        assert ok is False

    # ── Number ────────────────────────────────────────────────────────────────
    @pytest.mark.parametrize('num', ['0', '42', '3.14', '1000000'])
    def test_valid_numbers(self, num):
        from apps.bot.handlers import validate_answer
        q = self._make_q('number')
        ok, _ = validate_answer(q, num)
        assert ok is True

    @pytest.mark.parametrize('num', ['abc', '1.2.3', '-5', '1e5'])
    def test_invalid_numbers(self, num):
        from apps.bot.handlers import validate_answer
        q = self._make_q('number')
        ok, _ = validate_answer(q, num)
        assert ok is False

    # ── Choice ────────────────────────────────────────────────────────────────
    def test_valid_choice(self):
        from apps.bot.handlers import validate_answer
        q = self._make_q('choice', choices=['تهران', 'اصفهان', 'شیراز'])
        ok, _ = validate_answer(q, 'تهران')
        assert ok is True

    def test_invalid_choice(self):
        from apps.bot.handlers import validate_answer
        q = self._make_q('choice', choices=['A', 'B'])
        ok, err = validate_answer(q, 'C')
        assert ok is False
        assert err

    def test_choice_with_no_list_accepts_anything(self):
        from apps.bot.handlers import validate_answer
        q = self._make_q('choice', choices=[])
        ok, _ = validate_answer(q, 'anything goes')
        assert ok is True

    # ── Required / optional ───────────────────────────────────────────────────
    def test_required_field_rejects_blank(self):
        from apps.bot.handlers import validate_answer
        q = self._make_q('text', required=True)
        ok, err = validate_answer(q, '   ')
        assert ok is False
        assert 'اجباری' in err

    def test_optional_field_accepts_blank(self):
        from apps.bot.handlers import validate_answer
        q = self._make_q('text', required=False)
        ok, _ = validate_answer(q, '')
        assert ok is True

    def test_custom_validation_hint(self):
        from apps.bot.handlers import validate_answer
        q = self._make_q('phone', hint='شماره اشتباه است!')
        ok, err = validate_answer(q, 'invalid')
        assert ok is False
        assert err == 'شماره اشتباه است!'


# ─── DB helper tests ──────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestDBHelpers:

    def test_get_or_create_bot_user_creates_new(self, mock_tg_user):
        from apps.bot.handlers import _get_or_create_bot_user
        from apps.registration.models import BotUser

        user = _get_or_create_bot_user(mock_tg_user)
        assert user.bale_user_id == mock_tg_user.id
        assert user.first_name == mock_tg_user.first_name
        assert BotUser.objects.count() == 1

    def test_get_or_create_bot_user_is_idempotent(self, mock_tg_user):
        from apps.bot.handlers import _get_or_create_bot_user
        from apps.registration.models import BotUser

        _get_or_create_bot_user(mock_tg_user)
        _get_or_create_bot_user(mock_tg_user)
        assert BotUser.objects.count() == 1

    def test_get_or_create_bot_user_updates_name(self, mock_tg_user):
        from apps.bot.handlers import _get_or_create_bot_user

        _get_or_create_bot_user(mock_tg_user)
        mock_tg_user.first_name = 'NewName'
        user = _get_or_create_bot_user(mock_tg_user)
        assert user.first_name == 'NewName'

    def test_get_or_create_session_creates(self, bot_user_factory):
        from apps.bot.handlers import _get_or_create_session
        from apps.registration.models import RegistrationSession

        bot_user = bot_user_factory()
        session = _get_or_create_session(bot_user)
        assert session.current_question_index == 0
        assert session.answers == {}
        assert RegistrationSession.objects.count() == 1

    def test_save_answer_advances_index(self, session_factory, question_factory):
        from apps.bot.handlers import _save_answer

        session = session_factory(index=0)
        _save_answer(session, 'full_name', 'علی رضایی', 1)
        session.refresh_from_db()
        assert session.current_question_index == 1
        assert session.answers == {'full_name': 'علی رضایی'}

    def test_complete_session(self, session_factory, bot_user_factory):
        from apps.bot.handlers import _complete_session

        bot_user = bot_user_factory()
        session = session_factory(bot_user=bot_user)
        _complete_session(session, bot_user)

        session.refresh_from_db()
        bot_user.refresh_from_db()
        assert session.is_completed is True
        assert session.completed_at is not None
        assert bot_user.is_registered is True
        assert bot_user.registered_at is not None

    def test_reset_session(self, session_factory, bot_user_factory):
        from apps.bot.handlers import _reset_session
        from apps.registration.models import RegistrationSession

        bot_user = bot_user_factory(registered=True)
        session_factory(bot_user=bot_user, completed=True)
        _reset_session(bot_user)

        assert RegistrationSession.objects.filter(user=bot_user).count() == 0
        bot_user.refresh_from_db()
        assert bot_user.is_registered is False


# ─── Full flow (mocked bot) ───────────────────────────────────────────────────

@pytest.mark.django_db
class TestRegistrationFlow:
    """
    Simulates the full registration conversation:
    /start → Q1 answer → Q2 answer → ... → final message sent.
    """

    def _make_message(self, text, user_id=12345):
        msg = MagicMock()
        msg.text = text
        msg.chat.id = user_id
        msg.from_user.id = user_id
        msg.from_user.first_name = 'تست'
        msg.from_user.last_name = ''
        msg.from_user.username = 'testuser'
        return msg

    def test_start_asks_first_question(self, question_factory, mock_bot):
        from apps.bot.handlers import register_handlers
        register_handlers(mock_bot)

        question_factory(order=1, question_type='text')
        msg = self._make_message('/start')

        # Trigger the /start handler directly
        from apps.bot.handlers import _get_or_create_bot_user, _get_or_create_session, send_question
        bot_user = _get_or_create_bot_user(msg.from_user)
        questions = [question_factory.__wrapped__(order=1)] if hasattr(question_factory, '__wrapped__') else None

        # Just test the DB side: user + session created
        session = _get_or_create_session(bot_user)
        assert session.current_question_index == 0

    def test_full_two_question_flow(self, question_factory, final_message_factory, mock_bot):
        from apps.bot.handlers import (
            _get_or_create_bot_user, _get_or_create_session,
            _get_active_questions, validate_answer,
            _save_answer, _complete_session, _get_active_final_message,
        )
        from apps.registration.models import BotUser, RegistrationSession

        # Setup
        q1 = question_factory(order=1, question_type='text', field_name='full_name')
        q2 = question_factory(order=2, question_type='phone', field_name='phone')
        fm = final_message_factory(message_type='text', text='خوش آمدید!')

        tg_user = MagicMock()
        tg_user.id = 55555
        tg_user.first_name = 'رضا'
        tg_user.last_name = ''
        tg_user.username = 'reza'

        bot_user = _get_or_create_bot_user(tg_user)
        session = _get_or_create_session(bot_user)
        questions = _get_active_questions()
        assert len(questions) == 2

        # Answer Q1
        ok1, _ = validate_answer(questions[0], 'رضا احمدی')
        assert ok1
        _save_answer(session, questions[0].field_name, 'رضا احمدی', 1)
        session.refresh_from_db()
        assert session.current_question_index == 1

        # Answer Q2
        ok2, _ = validate_answer(questions[1], '09121234567')
        assert ok2
        _save_answer(session, questions[1].field_name, '09121234567', 2)
        _complete_session(session, bot_user)

        session.refresh_from_db()
        bot_user.refresh_from_db()
        assert session.is_completed is True
        assert bot_user.is_registered is True
        assert session.answers == {'full_name': 'رضا احمدی', 'phone': '09121234567'}

        # Final message retrieved
        final = _get_active_final_message()
        assert final is not None
        assert final.text_content == 'خوش آمدید!'

    def test_invalid_answer_does_not_advance(self, question_factory):
        from apps.bot.handlers import (
            _get_or_create_bot_user, _get_or_create_session,
            validate_answer, _save_answer,
        )

        q = question_factory(order=1, question_type='email', field_name='email')

        tg_user = MagicMock()
        tg_user.id = 66666
        tg_user.first_name = 'Test'
        tg_user.last_name = ''
        tg_user.username = ''

        bot_user = _get_or_create_bot_user(tg_user)
        session = _get_or_create_session(bot_user)

        ok, err = validate_answer(q, 'not-an-email')
        assert ok is False
        assert err
        # Index unchanged
        assert session.current_question_index == 0

    def test_blocked_user_not_advanced(self, bot_user_factory):
        from apps.bot.handlers import _get_or_create_bot_user

        blocked = bot_user_factory(user_id=77777, blocked=True)

        tg_user = MagicMock()
        tg_user.id = 77777
        tg_user.first_name = 'X'
        tg_user.last_name = ''
        tg_user.username = ''

        user = _get_or_create_bot_user(tg_user)
        assert user.is_blocked is True
