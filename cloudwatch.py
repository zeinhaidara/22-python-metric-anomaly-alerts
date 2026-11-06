"""Thin CloudWatch metric adapter.

Kept to exactly what the detector needs: one metric's recent data points, oldest first,
following NextToken pagination. Isolated here so another provider (Azure Monitor, GCP
Monitoring - both out of scope for this build) could be dropped in behind the same
fetch_metric_values(client, metric_cfg) shape later.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


def _build_query(metric_cfg: dict) -> dict:
    return {
        "Id": "m1",
        "MetricStat": {
            "Metric": {
                "Namespace": metric_cfg["namespace"],
                "MetricName": metric_cfg["metric_name"],
                "Dimensions": [
                    {"Name": name, "Value": value} for name, value in metric_cfg.get("dimensions", {}).items()
                ],
            },
            "Period": metric_cfg["period_seconds"],
            "Stat": metric_cfg["stat"],
        },
        "ReturnData": True,
    }


def fetch_metric_values(client, metric_cfg: dict, now: datetime | None = None) -> list[float]:
    """Pull one metric's recent values, oldest first, paging through NextToken as needed."""
    now = now or datetime.now(timezone.utc)
    start = now - timedelta(seconds=metric_cfg["window_seconds"])
    query = _build_query(metric_cfg)

    points: list[tuple[datetime, float]] = []
    next_token = None
    while True:
        kwargs = {"MetricDataQueries": [query], "StartTime": start, "EndTime": now}
        if next_token:
            kwargs["NextToken"] = next_token

        response = client.get_metric_data(**kwargs)
        for result in response.get("MetricDataResults", []):
            points.extend(zip(result.get("Timestamps", []), result.get("Values", [])))

        next_token = response.get("NextToken")
        if not next_token:
            break

    points.sort(key=lambda pair: pair[0])
    return [value for _, value in points]
