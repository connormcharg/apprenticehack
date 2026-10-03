# Events now live in the communities app, so the old global event models go.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('fivenine', '0007_remove_task_parent'),
    ]

    operations = [
        migrations.DeleteModel(
            name='EventAttendee',
        ),
        migrations.DeleteModel(
            name='CommunityEvent',
        ),
    ]
