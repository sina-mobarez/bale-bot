"""
Tests for registration app models.
"""
import pytest
from django.utils import timezone


@pytest.mark.django_db
class TestQuestion:
    def test_create_basic(self, question_factory):
        from apps.registration.models import Question
        q = question_factory(order=1, question_type='text')
        assert q.pk is not None
        assert q.is_active is True
        assert q.is_required is True

    def test_str_representation(self, question_factory):
        q = question_factory(order=1)
        assert '[1]' in str(q)

    def test_get_choices_list_empty_for_text(self, question_factory):
        q = question_factory(order=1, question_type='text')
        assert q.get_choices_list() == []

    def test_get_choices_list_for_choice_type(self, question_factory):
        q = question_factory(
            order=1,
            question_type='choice',
            choices='گزینه اول\nگزینه دوم\nگزینه سوم',
        )
        assert q.get_choices_list() == ['گزینه اول', 'گزینه دوم', 'گزینه سوم']

    def test_get_choices_list_strips_whitespace(self, question_factory):
        q = question_factory(
            order=1,
            question_type='choice',
            choices='  A  \n  B  \n',
        )
        assert q.get_choices_list() == ['A', 'B']

    def test_active_questions_ordered(self, question_factory):
        from apps.registration.models import Question
        question_factory(order=3)
        question_factory(order=1)
        question_factory(order=2)
        qs = list(Question.objects.filter(is_active=True).order_by('order'))
        assert [q.order for q in qs] == [1, 2, 3]

    def test_inactive_questions_excluded(self, question_factory):
        from apps.registration.models import Question
        question_factory(order=1, is_active=True)
        question_factory(order=2, is_active=False)
        active = Question.objects.filter(is_active=True)
        assert active.count() == 1


@pytest.mark.django_db
class TestFinalMessage:
    def test_only_one_active(self, final_message_factory):
        from apps.registration.models import FinalMessage
        fm1 = final_message_factory(active=True)
        fm2 = final_message_factory(active=True)
        # fm1 should now be inactive
        fm1.refresh_from_db()
        assert fm1.is_active is False
        assert fm2.is_active is True

    def test_active_count_never_exceeds_one(self, final_message_factory):
        from apps.registration.models import FinalMessage
        for _ in range(5):
            final_message_factory(active=True)
        assert FinalMessage.objects.filter(is_active=True).count() == 1

    def test_str_shows_active_status(self, final_message_factory):
        fm = final_message_factory(active=True)
        assert '✅' in str(fm)

    def test_str_shows_inactive_status(self, final_message_factory):
        fm = final_message_factory(active=False)
        assert '❌' in str(fm)


@pytest.mark.django_db
class TestBotUser:
    def test_create(self, bot_user_factory):
        user = bot_user_factory(user_id=12345)
        assert user.bale_user_id == 12345
        assert user.is_registered is False
        assert user.is_blocked is False

    def test_full_name_property(self, bot_user_factory):
        user = bot_user_factory()
        user.first_name = 'علی'
        user.last_name = 'رضایی'
        user.save()
        assert user.full_name == 'علی رضایی'

    def test_full_name_empty_last_name(self, bot_user_factory):
        user = bot_user_factory()
        user.first_name = 'علی'
        user.last_name = ''
        user.save()
        assert user.full_name == 'علی'

    def test_unique_bale_user_id(self, bot_user_factory):
        from django.db import IntegrityError
        from apps.registration.models import BotUser
        bot_user_factory(user_id=99999)
        with pytest.raises(IntegrityError):
            BotUser.objects.create(bale_user_id=99999, first_name='Dup')


@pytest.mark.django_db
class TestRegistrationSession:
    def test_create(self, session_factory, bot_user_factory):
        user = bot_user_factory()
        session = session_factory(bot_user=user)
        assert session.current_question_index == 0
        assert session.answers == {}
        assert session.is_completed is False

    def test_one_session_per_user(self, session_factory, bot_user_factory):
        from apps.registration.models import RegistrationSession
        from django.db import IntegrityError
        user = bot_user_factory()
        session_factory(bot_user=user)
        with pytest.raises(IntegrityError):
            RegistrationSession.objects.create(
                user=user,
                current_question_index=0,
                answers={},
            )

    def test_str_shows_progress(self, session_factory):
        session = session_factory(index=2, completed=False)
        assert '3' in str(session)   # "سوال 3" (1-indexed display)

    def test_str_shows_completed(self, session_factory):
        session = session_factory(completed=True)
        assert 'تکمیل' in str(session)
