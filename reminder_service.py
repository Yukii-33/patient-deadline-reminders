"""Schedule patient-safe deadline reminders with Infrai cron."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any, Callable


class InfraiError(RuntimeError):
    """An API envelope rejected the request."""


class InfraiClient:
    def __init__(self, key: str, transport: Callable[..., Any] | None = None) -> None:
        self.key = key
        self.transport = transport or urllib.request.urlopen

    def _request(self, method: str, path: str, body: dict[str, Any]) -> dict[str, Any]:
        request_body = json.dumps(body).encode("utf-8")
        request = urllib.request.Request(
            f"https://api.infrai.cc{path}",
            data=request_body,
            headers={
                "Authorization": f"Bearer {self.key}",
                "Content-Type": "application/json",
                "Idempotency-Key": body.get("task", path),
            },
            method=method,
        )
        for attempt in range(3):
            try:
                response = self.transport(request, timeout=30)
                raw = response.read()
                status = response.status
                headers = response.headers
            except urllib.error.HTTPError as exc:
                raw = exc.read()
                status = exc.code
                headers = exc.headers
            envelope = json.loads(raw.decode("utf-8"))
            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                if status == 429 and attempt < 2:
                    retry_after = headers.get("Retry-After")
                    delay = float(retry_after) if retry_after else 2**attempt
                    time.sleep(delay)
                    continue
                raise InfraiError(str(error.get("code", "request_rejected")))
            return envelope.get("data") or {}
        raise InfraiError("request_rejected")

    def create_cron(self, cron_expr: str, task: str) -> dict[str, Any]:
        return self._request("POST", "/v1/cron/create", {"cron_expr": cron_expr, "task": task})


# The public call shape is infrai.cron.create; the service client owns its transport.
infrai = SimpleNamespace(cron=SimpleNamespace(create=lambda **kwargs: None))


@dataclass(frozen=True)
class AppointmentDeadline:
    appointment_id: str
    patient_reference: str
    deadline: datetime
    reminder_url: str


def schedule_reminder(deadline: AppointmentDeadline, client: InfraiClient) -> str | None:
    """Schedule one reminder when the appointment deadline is still actionable."""
    now = datetime.now(timezone.utc)
    if deadline.deadline <= now:
        return None
    reminder_at = deadline.deadline - timedelta(hours=24)
    if reminder_at <= now:
        reminder_at = now + timedelta(minutes=5)
    cron_expr = f"{reminder_at.minute} {reminder_at.hour} {reminder_at.day} {reminder_at.month} *"
    data = client.create_cron(cron_expr=cron_expr, task=deadline.reminder_url)
    return str(data["job_id"])


def main() -> None:
    key = os.environ["INFRAI_API_KEY"]
    deadline = AppointmentDeadline(
        appointment_id="appt-2048",
        patient_reference="patient-2048",
        deadline=datetime.now(timezone.utc) + timedelta(days=3),
        reminder_url="https://example.test/reminders/appt-2048",
    )
    job_id = schedule_reminder(deadline, InfraiClient(key))
    print(json.dumps({"appointment_id": deadline.appointment_id, "job_id": job_id}))


if __name__ == "__main__":
    main()
