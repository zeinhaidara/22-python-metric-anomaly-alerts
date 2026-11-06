"""Entry point: config -> CloudWatch -> detector -> Slack.

Exit codes: 0 no anomalies, 2 anomalies found, 1 error.
"""

from __future__ import annotations

import argparse
import json
import sys

import boto3

from cloudwatch import fetch_metric_values
from detector import detect
from slack import build_payload
from slack import post as slack_post

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_ANOMALY = 2


def load_config(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def run(config: list[dict], client, dry_run: bool, post_fn=slack_post) -> int:
    found_anomaly = False
    for metric_cfg in config:
        values = fetch_metric_values(client, metric_cfg)
        result = detect(values, metric_cfg["z_score_threshold"])
        if not result.is_anomaly:
            continue

        found_anomaly = True
        payload = build_payload(metric_cfg["metric_name"], result, metric_cfg["recommended_action"])
        if dry_run:
            print(json.dumps(payload, indent=2))
            continue
        # A failed post only warns (inside post_fn) - it never hides that an anomaly happened.
        post_fn(payload)

    return EXIT_ANOMALY if found_anomaly else EXIT_OK


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", help="path to a metrics config JSON file")
    parser.add_argument("--dry-run", action="store_true", help="print Slack payloads, never post")
    parser.add_argument("--region", default="us-east-1")
    args = parser.parse_args(argv)

    try:
        config = load_config(args.config)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR

    try:
        client = boto3.client("cloudwatch", region_name=args.region)
        return run(config, client, args.dry_run)
    except Exception as exc:
        # Broad on purpose: any CloudWatch/network failure here becomes exit 1, not a traceback.
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
