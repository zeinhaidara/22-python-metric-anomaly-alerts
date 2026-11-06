"""Slack Block Kit alert payload and poster."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from detector import DetectionResult


def build_payload(metric_name: str, result: DetectionResult, recommended_action: str) -> dict:
    return {
        "blocks": [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"Anomaly detected: {metric_name}"},
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Current value:*\n{result.value:.2f}"},
                    {
                        "type": "mrkdwn",
                        "text": (
                            f"*Expected range:*\n{result.expected_low:.2f} - {result.expected_high:.2f}"
                        ),
                    },
                    {"type": "mrkdwn", "text": f"*Z-score:*\n{result.z_score:.2f}"},
                ],
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Recommended action:*\n{recommended_action}"},
            },
        ]
    }


def post(payload: dict) -> bool:
    """Post to the webhook named by SLACK_WEBHOOK_URL. Returns True on success.

    The URL itself is never logged or printed, on any path - only the HTTP status (or the
    connection error) is, so a failure is visible without leaking the webhook.
    """
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook_url:
        print("warning: SLACK_WEBHOOK_URL is not set, skipping Slack post")
        return False

    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(webhook_url, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            if response.status >= 300:
                print(f"warning: slack post failed with status {response.status}")
                return False
            return True
    except urllib.error.HTTPError as exc:
        print(f"warning: slack post failed with status {exc.code}")
        return False
    except urllib.error.URLError as exc:
        print(f"warning: slack post failed: {exc.reason}")
        return False
