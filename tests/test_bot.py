"""
Tests for the Bale Registration Bot.

Run with:
  python manage.py test tests --verbosity=2

Tests cover:
  - Model creation and constraints
  - FinalMessage single-active enforcement
  - Validators (phone, email, number, choice, text)
  - Bot flow helpers (_get_or_create_bot_user, _save_answer, etc.)
  - Admin CSV export
  - Management commands (seed, export)
"""
from unittest.mock import MagicMock, patch, call
from django.test import TestCase, RequestFactory
from django.utils import timezone

from apps.registration.models import (
    Question, FinalMessage, BotUser, RegistrationSession,
)
from apps.bot.handlers import (
    validate_answer,
    _get_or_create_bot_user,
    _get_or_create_session,
    _save_answer,
    _complete_session,
    _reset_session,
)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def make_question(**kwargs):
    defaults = dict(
        order=1,
        text='سوال تست',
        field_name='test_field',
        question_type=Question.QuestionType.TEXT,
        is_required=True,
        is_active=True,
    )
    defaults.update(kwargs)
    return Question.objects.create(**defaults)


def make_bot_user(**kwargs):
    defaults = dict(bale_user_id=12345, first_name='علی', last_name='تست')
    defaults.update(kwargs)
    return BotUser.objects.create(**defaults)


def make_tg_user(uid=12345, first='علی', last='تست', username='ali_test'):
    u = MagicMock()
    u.id = uid
    u.first_name = first
    u.last_name = last
    u.username = username
    return u


# ─── Model tests ──────────────────────────────────────────────────────────────

class QuestionModelTest(TestCase):

    def test_create_text_question(self):
        q = make_question()
        self.assertEqual(q.field_name, 'test_field')
        self.assertTrue(q.is_active)

    def test_ordering_by_order_field(self):
        make_question(order=3, field_name='c')
        make_question(order=1, field_name='a')
        make_question(order=2, field_name='b')
        qs = list(Question.objects.all())
        self.assertEqual([q.order for q in qs], [1, 2, 3])

    def test_get_choices_list_for_choice_type(self):
        q = make_question(
            question_type=Question.QuestionType.CHOICE,
            choices='گزینه ۱\nگزینه ۲\n\nگزینه ۳',
        )
        choices = q.get_choices_list()
        self.assertEqual(choices, ['گزینه ۱', 'گزینه ۲', 'گزینه ۳'])

    def test_get_choices_list_for_non_choice_type(self):
        q = make_question(question_type=Question.QuestionType.TEXT)
        self.assertEqual(q.get_choices_list(), [])

    def test_unique_order_constraint(self):
        from django.db import IntegrityError
        make_question(order=1, field_name='a')
        with self.assertRaises(IntegrityError):
            make_question(order=1, field_name='b')

    def test_unique_field_name_constraint(self):
        from django.db import IntegrityError
        make_question(field_name='dup')
        with self.assertRaises(IntegrityError):
            make_question(order=2, field_name='dup')


class FinalMessageModelTest(TestCase):

    def test_only_one_active_at_a_time(self):
        fm1 = FinalMessage.objects.create(
            title='پیام ۱',
            message_type=FinalMessage.MessageType.TEXT,
            text_content='متن ۱',
            is_active=True,
        )
        fm2 = FinalMessage.objects.create(
            title='پیام ۲',
            message_type=FinalMessage.MessageType.TEXT,
            text_content='متن ۲',
            is_active=True,
        )
        fm1.refresh_from_db()
        self.assertFalse(fm1.is_active, 'fm1 should be deactivated when fm2 is activated')
        self.assertTrue(fm2.is_active)

    def test_string_representation(self):
        fm = FinalMessage.objects.create(
            title='تست',
            message_type=FinalMessage.MessageType.TEXT,
            text_content='سلام',
            is_active=True,
        )
        self.assertIn('تست', str(fm))
        self.assertIn('فعال', str(fm))


class BotUserModelTest(TestCase):

    def test_full_name_property(self):
        user = BotUser.objects.create(
            bale_user_id=1,
            first_name='محمد',
            last_name='احمدی',
        )
        self.assertEqual(user.full_name, 'محمد احمدی')

    def test_full_name_with_only_first_name(self):
        user = BotUser.objects.create(bale_user_id=2, first_name='علی')
        self.assertEqual(user.full_name, 'علی')

    def test_str_with_username(self):
        user = BotUser.objects.create(
            bale_user_id=3, first_name='سارا', username='sara99',
        )
        self.assertIn('@sara99', str(user))

    def test_unique_bale_user_id(self):
        from django.db import IntegrityError
        BotUser.objects.create(bale_user_id=999)
        with self.assertRaises(IntegrityError):
            BotUser.objects.create(bale_user_id=999)


# ─── Validator tests ──────────────────────────────────────────────────────────

class ValidatorTest(TestCase):

    def _q(self, qtype, required=True, hint='', choices=''):
        return Question(
            order=1,
            text='سوال',
            field_name='f',
            question_type=qtype,
            is_required=required,
            validation_hint=hint,
            choices=choices,
        )

    # Phone
    def test_valid_phones(self):
        q = self._q(Question.QuestionType.PHONE)
        for phone in ['09123456789', '09001234567', '+989123456789', '00989123456789']:
            ok, _ = validate_answer(q, phone)
            self.assertTrue(ok, f'{phone} should be valid')

    def test_invalid_phones(self):
        q = self._q(Question.QuestionType.PHONE)
        for phone in ['1234567', '08123456789', 'notaphone', '091234567']:
            ok, msg = validate_answer(q, phone)
            self.assertFalse(ok, f'{phone} should be invalid')
            self.assertTrue(len(msg) > 0)

    # Email
    def test_valid_emails(self):
        q = self._q(Question.QuestionType.EMAIL)
        for email in ['a@b.com', 'user.name+tag@domain.co', 'test@sub.domain.org']:
            ok, _ = validate_answer(q, email)
            self.assertTrue(ok, f'{email} should be valid')

    def test_invalid_emails(self):
        q = self._q(Question.QuestionType.EMAIL)
        for email in ['notanemail', '@domain.com', 'user@', 'user @domain.com']:
            ok, _ = validate_answer(q, email)
            self.assertFalse(ok, f'{email} should be invalid')

    # Number
    def test_valid_numbers(self):
        q = self._q(Question.QuestionType.NUMBER)
        for num in ['42', '3.14', '0', '1000000']:
            ok, _ = validate_answer(q, num)
            self.assertTrue(ok, f'{num} should be valid')

    def test_invalid_numbers(self):
        q = self._q(Question.QuestionType.NUMBER)
        for num in ['abc', '12abc', '-5', '1,000']:
            ok, _ = validate_answer(q, num)
            self.assertFalse(ok, f'{num} should be invalid')

    # Choice
    def test_valid_choice(self):
        q = self._q(Question.QuestionType.CHOICE, choices='A\nB\nC')
        ok, _ = validate_answer(q, 'B')
        self.assertTrue(ok)

    def test_invalid_choice(self):
        q = self._q(Question.QuestionType.CHOICE, choices='A\nB\nC')
        ok, msg = validate_answer(q, 'X')
        self.assertFalse(ok)
        self.assertTrue(len(msg) > 0)

    # Required
    def test_required_empty_fails(self):
        q = self._q(Question.QuestionType.TEXT, required=True)
        ok, msg = validate_answer(q, '   ')
        self.assertFalse(ok)
        self.assertIn('اجباری', msg)

    def test_not_required_empty_passes(self):
        q = self._q(Question.QuestionType.TEXT, required=False)
        ok, _ = validate_answer(q, '')
        self.assertTrue(ok)

    # Custom hint
    def test_custom_validation_hint_used(self):
        q = self._q(Question.QuestionType.PHONE, hint='شماره اشتباه است!')
        ok, msg = validate_answer(q, 'bad')
        self.assertFalse(ok)
        self.assertEqual(msg, 'شماره اشتباه است!')


# ─── Bot flow helper tests ────────────────────────────────────────────────────

class BotFlowHelperTest(TestCase):

    def test_get_or_create_bot_user_creates_new(self):
        tg = make_tg_user(uid=55555)
        user = _get_or_create_bot_user(tg)
        self.assertEqual(user.bale_user_id, 55555)
        self.assertEqual(user.first_name, 'علی')
        self.assertEqual(BotUser.objects.count(), 1)

    def test_get_or_create_bot_user_updates_name(self):
        BotUser.objects.create(bale_user_id=55555, first_name='قدیمی')
        tg = make_tg_user(uid=55555, first='جدید')
        user = _get_or_create_bot_user(tg)
        self.assertEqual(user.first_name, 'جدید')
        self.assertEqual(BotUser.objects.count(), 1)

    def test_get_or_create_session_creates(self):
        bot_user = make_bot_user()
        session = _get_or_create_session(bot_user)
        self.assertEqual(session.current_question_index, 0)
        self.assertEqual(session.answers, {})
        self.assertFalse(session.is_completed)

    def test_save_answer_advances_index(self):
        bot_user = make_bot_user()
        session = _get_or_create_session(bot_user)
        _save_answer(session, 'full_name', 'علی احمدی', 1)
        session.refresh_from_db()
        self.assertEqual(session.answers['full_name'], 'علی احمدی')
        self.assertEqual(session.current_question_index, 1)

    def test_complete_session(self):
        bot_user = make_bot_user()
        session = _get_or_create_session(bot_user)
        _complete_session(session, bot_user)
        session.refresh_from_db()
        bot_user.refresh_from_db()
        self.assertTrue(session.is_completed)
        self.assertIsNotNone(session.completed_at)
        self.assertTrue(bot_user.is_registered)
        self.assertIsNotNone(bot_user.registered_at)

    def test_reset_session(self):
        bot_user = make_bot_user(is_registered=True)
        _get_or_create_session(bot_user)
        _reset_session(bot_user)
        bot_user.refresh_from_db()
        self.assertFalse(bot_user.is_registered)
        self.assertIsNone(bot_user.registered_at)
        self.assertEqual(RegistrationSession.objects.filter(user=bot_user).count(), 0)


# ─── Full flow simulation ─────────────────────────────────────────────────────

class FullFlowSimulationTest(TestCase):
    """
    Simulate a user going through the full registration flow without
    actually connecting to Bale. Uses mock bot object.
    """

    def setUp(self):
        Question.objects.create(
            order=1, text='نام شما؟', field_name='full_name',
            question_type=Question.QuestionType.TEXT, is_active=True,
        )
        Question.objects.create(
            order=2, text='شماره موبایل؟', field_name='phone',
            question_type=Question.QuestionType.PHONE, is_active=True,
        )
        Question.objects.create(
            order=3, text='شهر؟', field_name='city',
            question_type=Question.QuestionType.CHOICE,
            choices='تهران\nاصفهان', is_active=True,
        )
        FinalMessage.objects.create(
            title='پیام پایانی',
            message_type=FinalMessage.MessageType.TEXT,
            text_content='ثبت‌نام کامل شد!',
            is_active=True,
        )

    def _make_message(self, uid, text):
        msg = MagicMock()
        msg.chat.id = uid
        msg.from_user.id = uid
        msg.from_user.first_name = 'کاربر'
        msg.from_user.last_name = 'تست'
        msg.from_user.username = f'user_{uid}'
        msg.text = text
        return msg

    def test_full_registration_flow(self):
        from apps.bot.handlers import register_handlers
        import telebot
        from telebot import apihelper

        # Point at a dummy URL so no real network calls happen
        apihelper.API_URL = 'http://localhost:99999/bot{0}/{1}'

        bot = MagicMock(spec=telebot.TeleBot)
        register_handlers(bot)

        uid = 77777
        # /start — handled via registered decorator; simulate directly
        tg = make_tg_user(uid=uid, first='کاربر', last='تست')
        bot_user = _get_or_create_bot_user(tg)
        session = _get_or_create_session(bot_user)

        questions = list(Question.objects.filter(is_active=True).order_by('order'))

        # Answer Q1 — name
        ok, _ = validate_answer(questions[0], 'علی رضایی')
        self.assertTrue(ok)
        _save_answer(session, 'full_name', 'علی رضایی', 1)

        # Answer Q2 — phone (valid)
        ok, _ = validate_answer(questions[1], '09123456789')
        self.assertTrue(ok)
        _save_answer(session, 'phone', '09123456789', 2)

        # Answer Q2 — phone (invalid — should fail)
        ok2, msg = validate_answer(questions[1], 'bad_phone')
        self.assertFalse(ok2)

        # Answer Q3 — city (valid choice)
        ok, _ = validate_answer(questions[2], 'تهران')
        self.assertTrue(ok)
        _save_answer(session, 'city', 'تهران', 3)

        # Complete session
        _complete_session(session, bot_user)

        bot_user.refresh_from_db()
        session.refresh_from_db()

        self.assertTrue(bot_user.is_registered)
        self.assertTrue(session.is_completed)
        self.assertEqual(session.answers['full_name'], 'علی رضایی')
        self.assertEqual(session.answers['phone'], '09123456789')
        self.assertEqual(session.answers['city'], 'تهران')


# ─── Admin CSV export test ────────────────────────────────────────────────────

class AdminCsvExportTest(TestCase):

    def setUp(self):
        from django.contrib.auth.models import User
        self.admin_user = User.objects.create_superuser(
            username='admin', password='admin123', email='a@a.com',
        )
        self.client.force_login(self.admin_user)

        Question.objects.create(
            order=1, field_name='full_name', text='نام',
            question_type=Question.QuestionType.TEXT, is_active=True,
        )
        user = BotUser.objects.create(
            bale_user_id=111, first_name='تست', is_registered=True,
        )
        session = RegistrationSession.objects.create(
            user=user, is_completed=True,
            answers={'full_name': 'تست کاربر'},
            current_question_index=1,
        )

    def test_export_all_csv_view_returns_200(self):
        response = self.client.get(
            '/admin/registration/botuser/export-all-csv/'
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/csv', response['Content-Type'])

    def test_export_csv_contains_user_data(self):
        response = self.client.get(
            '/admin/registration/botuser/export-all-csv/'
        )
        content = response.content.decode('utf-8-sig')
        self.assertIn('تست', content)
        self.assertIn('111', content)


# ─── Seed command test ────────────────────────────────────────────────────────

class SeedCommandTest(TestCase):

    def test_seed_creates_questions_and_final_message(self):
        from django.core.management import call_command
        call_command('seed_sample_data', verbosity=0)
        self.assertGreater(Question.objects.count(), 0)
        self.assertEqual(FinalMessage.objects.filter(is_active=True).count(), 1)

    def test_seed_reset_clears_existing(self):
        from django.core.management import call_command
        call_command('seed_sample_data', verbosity=0)
        first_count = Question.objects.count()
        call_command('seed_sample_data', reset=True, verbosity=0)
        self.assertEqual(Question.objects.count(), first_count)


# ─── Export registrations command test ───────────────────────────────────────

class ExportCommandTest(TestCase):

    def setUp(self):
        Question.objects.create(
            order=1, field_name='name', text='نام',
            question_type=Question.QuestionType.TEXT, is_active=True,
        )
        u = BotUser.objects.create(bale_user_id=222, first_name='صادق', is_registered=True)
        RegistrationSession.objects.create(
            user=u, is_completed=True,
            answers={'name': 'صادق محمدی'},
            current_question_index=1,
            completed_at=timezone.now(),
        )

    def test_export_creates_csv_file(self):
        import os
        from django.core.management import call_command
        out_path = '/tmp/test_export.csv'
        call_command('export_registrations', output=out_path, verbosity=0)
        self.assertTrue(os.path.isfile(out_path))
        with open(out_path, encoding='utf-8-sig') as f:
            content = f.read()
        self.assertIn('صادق', content)
        os.remove(out_path)
