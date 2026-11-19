import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("finance", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Attendance",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("work_date", models.DateField(default=django.utils.timezone.localdate)),
                ("check_in", models.DateTimeField(default=django.utils.timezone.now)),
                ("check_out", models.DateTimeField(blank=True, null=True)),
                ("employee", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="attendance_records", to="finance.employee")),
            ],
            options={
                "ordering": ["-work_date", "-check_in"],
                "constraints": [
                    models.UniqueConstraint(fields=("employee", "work_date"), name="unique_employee_attendance_per_day"),
                    models.CheckConstraint(condition=models.Q(("check_out__isnull", True), ("check_out__gte", models.F("check_in")), _connector="OR"), name="attendance_checkout_after_checkin"),
                ],
            },
        ),
    ]