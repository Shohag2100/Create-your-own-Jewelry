# Merge migration to resolve conflicting 0005 migrations
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0005_add_position_to_milestonepayment'),
        ('payments', '0005_alter_milestone_position'),
    ]

    operations = [
        # This is an empty merge migration to unify the migration history.
    ]
