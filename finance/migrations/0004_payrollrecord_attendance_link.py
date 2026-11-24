from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0003_attendance_break_time_in_attendance_break_time_out_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='payrollrecord',
            name='days_worked',
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='payrollrecord',
            name='hours_worked',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=7),
        ),
        migrations.AlterField(
            model_name='payrollrecord',
            name='pay_type',
            field=models.CharField(choices=[('fixed', 'Fixed Amount'), ('percentage', 'Percentage of Gross Sales'), ('attendance', 'Attendance (days present × daily rate)')], default='fixed', max_length=12),
        ),
    ]
