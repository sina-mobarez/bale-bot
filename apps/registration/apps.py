import logging
from django.apps import AppConfig

logger = logging.getLogger(__name__)


def _on_scheduled_message_saved(sender, instance, **kwargs):
    if instance.is_sent:
        return
    try:
        from apps.registration.tasks import dispatch_scheduled_message
        dispatch_scheduled_message.apply_async(
            args=[instance.pk],
            eta=instance.scheduled_time,
        )
        logger.info(
            f'Scheduled send task for ScheduledMessage pk={instance.pk} at {instance.scheduled_time}'
        )
    except Exception as e:
        logger.error(f'Could not schedule task for ScheduledMessage pk={instance.pk}: {e}')


class RegistrationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.registration'
    verbose_name = 'ثبت‌نام'

    def ready(self):
        from django.db.models.signals import post_save
        from apps.registration.models import ScheduledMessage
        post_save.connect(_on_scheduled_message_saved, sender=ScheduledMessage)
