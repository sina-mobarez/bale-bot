from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('registration', '0002_scheduledmessage_welcomemessage_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='scheduledmessage',
            name='send_to_all',
            field=models.BooleanField(
                default=False,
                help_text='اگر فعال باشد، پیام به همه کاربران (حتی آن‌هایی که ثبت‌نام کامل نکرده‌اند) ارسال می‌شود',
                verbose_name='ارسال به همه کاربران',
            ),
        ),
    ]
