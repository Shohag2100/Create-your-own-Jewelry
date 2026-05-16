# Generated migration: add position to MilestonePayment and populate from Milestone
from django.db import migrations, models


def forwards(apps, schema_editor):
    MilestonePayment = apps.get_model('payments', 'MilestonePayment')
    Milestone = apps.get_model('payments', 'Milestone')
    # add position to existing MilestonePayment rows based on related Milestone
    for mp in MilestonePayment.objects.all():
        try:
            if mp.milestone_id:
                m = Milestone.objects.get(pk=mp.milestone_id)
                mp.position = getattr(m, 'position', None)
                mp.save()
        except Exception:
            # ignore any issues for existing records
            pass


def backwards(apps, schema_editor):
    # no-op for backwards migration: field will be removed by schema migration if rolled back
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0004_add_three_milestones'),
    ]

    operations = [
        migrations.AddField(
            model_name='milestonepayment',
            name='position',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.RunPython(forwards, backwards),
    ]
