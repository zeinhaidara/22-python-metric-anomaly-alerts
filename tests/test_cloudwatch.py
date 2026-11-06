import unittest
from datetime import datetime, timedelta, timezone

from cloudwatch import fetch_metric_values


class FakeCloudWatchClient:
    """Returns pre-built pages in order, recording every call's kwargs for inspection."""

    def __init__(self, pages):
        self.pages = list(pages)
        self.calls = []

    def get_metric_data(self, **kwargs):
        self.calls.append(kwargs)
        return self.pages.pop(0)


class FetchMetricValuesTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.metric_cfg = {
            "namespace": "AWS/EC2",
            "metric_name": "CPUUtilization",
            "dimensions": {"InstanceId": "i-0123456789abcdef0"},
            "stat": "Average",
            "period_seconds": 300,
            "window_seconds": 3600,
        }

    def test_request_parameters_come_from_the_metric_config(self):
        client = FakeCloudWatchClient([{"MetricDataResults": [{"Timestamps": [], "Values": []}]}])
        fetch_metric_values(client, self.metric_cfg, now=self.now)

        self.assertEqual(len(client.calls), 1)
        query = client.calls[0]["MetricDataQueries"][0]
        self.assertEqual(query["MetricStat"]["Metric"]["Namespace"], "AWS/EC2")
        self.assertEqual(query["MetricStat"]["Metric"]["MetricName"], "CPUUtilization")
        self.assertEqual(
            query["MetricStat"]["Metric"]["Dimensions"],
            [{"Name": "InstanceId", "Value": "i-0123456789abcdef0"}],
        )
        self.assertEqual(query["MetricStat"]["Period"], 300)
        self.assertEqual(query["MetricStat"]["Stat"], "Average")
        self.assertEqual(client.calls[0]["EndTime"], self.now)
        self.assertEqual(client.calls[0]["StartTime"], self.now - timedelta(seconds=3600))

    def test_no_dimensions_produces_an_empty_dimensions_list(self):
        cfg = dict(self.metric_cfg)
        del cfg["dimensions"]
        client = FakeCloudWatchClient([{"MetricDataResults": [{"Timestamps": [], "Values": []}]}])
        fetch_metric_values(client, cfg, now=self.now)

        query = client.calls[0]["MetricDataQueries"][0]
        self.assertEqual(query["MetricStat"]["Metric"]["Dimensions"], [])

    def test_values_are_returned_oldest_first(self):
        t0 = self.now - timedelta(minutes=10)
        t1 = self.now - timedelta(minutes=5)
        client = FakeCloudWatchClient(
            [{"MetricDataResults": [{"Timestamps": [t1, t0], "Values": [2.0, 1.0]}]}]
        )
        values = fetch_metric_values(client, self.metric_cfg, now=self.now)
        self.assertEqual(values, [1.0, 2.0])

    def test_next_token_pagination_is_followed_until_absent(self):
        t0 = self.now - timedelta(minutes=10)
        t1 = self.now - timedelta(minutes=5)
        t2 = self.now - timedelta(minutes=1)
        client = FakeCloudWatchClient(
            [
                {
                    "MetricDataResults": [{"Timestamps": [t0], "Values": [1.0]}],
                    "NextToken": "page-2",
                },
                {
                    "MetricDataResults": [{"Timestamps": [t2, t1], "Values": [3.0, 2.0]}],
                },
            ]
        )

        values = fetch_metric_values(client, self.metric_cfg, now=self.now)

        self.assertEqual(len(client.calls), 2)
        self.assertNotIn("NextToken", client.calls[0])
        self.assertEqual(client.calls[1]["NextToken"], "page-2")
        self.assertEqual(values, [1.0, 2.0, 3.0])


if __name__ == "__main__":
    unittest.main()
