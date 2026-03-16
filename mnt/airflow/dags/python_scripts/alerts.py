"""
Centralized alert callbacks for Airflow DAGs.

Provides on_failure_callback functions that can be attached to any DAG or
individual task via default_args / task-level parameters.

Integrations supported
-----------------------
- Slack (webhook)  — configure SLACK_WEBHOOK_URL env var
- Email            — handled natively by Airflow (email_on_failure: True)

Usage in a DAG::

    from python_scripts.alerts import slack_alert

    default_args = {
        "email_on_failure": True,
        "on_failure_callback": slack_alert,
        ...
    }
"""

import logging
import os

logger = logging.getLogger(__name__)


def slack_alert(context: dict) -> None:
    """
    Post a failure notification to Slack via incoming webhook.

    Reads SLACK_WEBHOOK_URL from the environment.  If the variable is not
    set the function logs a warning and returns silently so the DAG run is
    not further impacted.
    """
    webhook_url = os.getenv("SLACK_WEBHOOK_URL")
    if not webhook_url:
        logger.warning("[Alerts] SLACK_WEBHOOK_URL not set — skipping Slack notification.")
        return

    dag_id       = context.get("dag").dag_id
    task_id      = context.get("task_instance").task_id
    run_id       = context.get("run_id", "unknown")
    log_url      = context.get("task_instance").log_url
    exception    = context.get("exception", "N/A")

    message = {
        "text": (
            f":red_circle: *Airflow task failed*\n"
            f"*DAG:* `{dag_id}`\n"
            f"*Task:* `{task_id}`\n"
            f"*Run ID:* `{run_id}`\n"
            f"*Error:* `{exception}`\n"
            f"*Logs:* {log_url}"
        )
    }

    try:
        import urllib.request, json as _json
        data = _json.dumps(message).encode("utf-8")
        req  = urllib.request.Request(
            webhook_url,
            data=data,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status != 200:
                logger.error(f"[Alerts] Slack webhook returned HTTP {resp.status}.")
    except Exception as exc:
        logger.error(f"[Alerts] Failed to send Slack alert: {exc}")
