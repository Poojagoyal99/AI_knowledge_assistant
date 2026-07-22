from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0003_passwordresetotp'),
    ]

    operations = [
        migrations.AddField(
            model_name='message',
            name='highlights',
            field=models.JSONField(blank=True, default=list),
        ),
    ]
