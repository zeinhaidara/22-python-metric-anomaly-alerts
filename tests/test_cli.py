import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cli import EXIT_ANOMALY, EXIT_ERROR, EXIT_OK, load_config, main, run


class FakeClient:
    """Always returns one page of values for whatever metric is asked for."""

    def __init__(self, values):
        self.values = values
        self.now = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def get_metric_data(self, **kwargs):
        timestamps = [self.now - timedelta(minutes=len(self.values) - i) for i in range(len(self.values))]
        return {"MetricDataResults": [{"Timestamps": timestamps, "Values": self.values}]}


def make_metric_cfg(**overrides):
    cfg = {
        "namespace": "AWS/EC2",
        "metric_name": "CPUUtilization",
        "dimensions": {"InstanceId": "i-0123456789abcdef0"},
        "stat": "Average",
        "period_seconds": 300,
        "window_seconds": 3600,
        "z_score_threshold": 3.0,
        "recommended_action": "Scale the instance group.",
    }
    cfg.update(overrides)
    return cfg


class LoadConfigTests(unittest.TestCase):
    def test_reads_json_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "metrics.json"
            path.write_text(json.dumps([make_metric_cfg()]))
            config = load_config(str(path))
        self.assertEqual(len(config), 1)
        self.assertEqual(config[0]["metric_name"], "CPUUtilization")


class RunTests(unittest.TestCase):
    def test_no_anomalies_returns_exit_ok(self):
        flat = [10.0, 10.1, 9.9, 10.0, 10.2, 10.1]
        client = FakeClient(flat)
        code = run([make_metric_cfg()], client, dry_run=False, post_fn=lambda payload: True)
        self.assertEqual(code, EXIT_OK)

    def test_anomaly_dry_run_prints_payload_and_never_posts(self):
        spiky = [10.0, 11.0, 9.0, 10.0, 10.5, 50.0]
        client = FakeClient(spiky)
        calls = []
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = run(
                [make_metric_cfg()],
                client,
                dry_run=True,
                post_fn=lambda payload: calls.append(payload) or True,
            )
        self.assertEqual(code, EXIT_ANOMALY)
        self.assertEqual(calls, [])
        self.assertIn("CPUUtilization", buf.getvalue())

    def test_anomaly_not_dry_run_calls_post_fn(self):
        spiky = [10.0, 11.0, 9.0, 10.0, 10.5, 50.0]
        client = FakeClient(spiky)
        calls = []
        code = run(
            [make_metric_cfg()],
            client,
            dry_run=False,
            post_fn=lambda payload: calls.append(payload) or True,
        )
        self.assertEqual(code, EXIT_ANOMALY)
        self.assertEqual(len(calls), 1)

    def test_slack_failure_does_not_hide_the_anomaly_exit_code(self):
        spiky = [10.0, 11.0, 9.0, 10.0, 10.5, 50.0]
        client = FakeClient(spiky)
        code = run([make_metric_cfg()], client, dry_run=False, post_fn=lambda payload: False)
        self.assertEqual(code, EXIT_ANOMALY)

    def test_one_anomalous_metric_among_several_still_flags_anomaly(self):
        flat = [10.0, 10.1, 9.9, 10.0, 10.2, 10.1]
        spiky = [10.0, 11.0, 9.0, 10.0, 10.5, 50.0]

        class MultiMetricClient:
            def get_metric_data(self, **kwargs):
                metric_name = kwargs["MetricDataQueries"][0]["MetricStat"]["Metric"]["MetricName"]
                values = spiky if metric_name == "ErrorRate" else flat
                now = datetime(2026, 1, 1, tzinfo=timezone.utc)
                timestamps = [now - timedelta(minutes=len(values) - i) for i in range(len(values))]
                return {"MetricDataResults": [{"Timestamps": timestamps, "Values": values}]}

        config = [make_metric_cfg(metric_name="CPUUtilization"), make_metric_cfg(metric_name="ErrorRate")]
        code = run(config, MultiMetricClient(), dry_run=False, post_fn=lambda payload: True)
        self.assertEqual(code, EXIT_ANOMALY)


class MainTests(unittest.TestCase):
    def test_missing_config_file_returns_exit_error(self):
        code = main(["/does/not/exist.json"])
        self.assertEqual(code, EXIT_ERROR)

    def test_invalid_json_returns_exit_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            path.write_text("{not valid json")
            code = main([str(path)])
        self.assertEqual(code, EXIT_ERROR)


if __name__ == "__main__":
    unittest.main()
