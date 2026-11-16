from datetime import datetime, timedelta, timezone

from reminder_service import AppointmentDeadline, schedule_reminder


class RecordingClient:
    def __init__(self):
        self.calls = []

    def create_cron(self, cron_expr, task):
        self.calls.append((cron_expr, task))
        return {"job_id": "job-1"}


def test_future_deadline_creates_a_reminder_job():
    client = RecordingClient()
    deadline = AppointmentDeadline(
        "appt-1",
        "patient-1",
        datetime.now(timezone.utc) + timedelta(days=2),
        "https://example.test/reminders/appt-1",
    )

    assert schedule_reminder(deadline, client) == "job-1"
    assert client.calls[0][1] == deadline.reminder_url


def test_past_deadline_is_not_scheduled():
    client = RecordingClient()
    deadline = AppointmentDeadline(
        "appt-2",
        "patient-2",
        datetime.now(timezone.utc) - timedelta(minutes=1),
        "https://example.test/reminders/appt-2",
    )

    assert schedule_reminder(deadline, client) is None
    assert client.calls == []
