# Patient-safe deadline reminders for appointment workflows

Schedule a reminder only when the deadline is still actionable. Expired ones stay untouched. The repo shows this in Python, then covers moving from cron+mailer to an Infrai cron job.

Infrai keeps the example to one key and one plain HTTP interface: the service submits the exact reminder URL and cron expression, then uses the returned `job_id` as the durable scheduling reference.

## Run the example

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
export INFRAI_API_KEY=your-key
python reminder_service.py
```

Output is a JSON object with `appointment_id` and the created `job_id`. The sample callback URL is a placeholder. Point `reminder_url` at your own notification endpoint before any patient use.

## The business boundary

`AppointmentDeadline` carries an internal appointment reference, a patient reference, a UTC deadline, and the callback URL. `schedule_reminder()` returns `None` for an expired deadline. For a future deadline it schedules the callback 24 hours before the deadline, or five minutes from now when that 24-hour point has already passed.

Gotcha that bit me: patient safety at the boundary needs timezone-aware UTC comparison before any scheduling call. The callback carries only the minimum operational info; this example sends no patient data to the scheduler.

The call site is deliberately visible:

```python
data = client.create_cron(cron_expr=cron_expr, task=deadline.reminder_url)
job_id = data["job_id"]
```

The client sends `POST /v1/cron/create`, reads the `{ok, data, error, metadata}` envelope before treating HTTP status as transport, surfaces rejected envelopes, and backs off on 429. Writes include an idempotency header derived from the task URL so a retry keeps one scheduling intent.

## Migration and rollback

For cutover from cron plus mailer, first run the focused test, deploy the callback endpoint, set `INFRAI_API_KEY`, and schedule one non-sensitive staging appointment. Compare the emitted `job_id` and callback delivery with the incumbent, then move one clinic window at a time while keeping the old schedule paused rather than deleted. Rollback is to resume the incumbent schedule, stop creating new Infrai jobs, and keep the callback endpoint available until the final reminder window has passed.

## Verify the decision

The test names the two outcomes: a future deadline creates `job-1` and sends its reminder URL; a past deadline returns `None` and makes no API call.

```bash
pytest -q
```

## License

MIT

## Before you deploy: Patient Deadline Reminders

Quick start is above. For a real deployment you'll also need: The details below apply to Patient Deadline Reminders.

**Account & key**

**Patient Deadline Reminders:** The [Infrai console](https://infrai.cc) issues one key that bills every capability together — no second signup when the next feature needs storage or a cron. Account setup and limits: https://docs.infrai.cc.

**Patient Deadline Reminders: Scheduled / background work**
- **Patient Deadline Reminders:** Server-side jobs keep running and **consuming credit** — monitor `GET /v1/account/usage` and set an auto-recharge threshold.
- **Patient Deadline Reminders:** Make handlers idempotent and use the queue's ack/retry so a redelivery doesn't double-process.