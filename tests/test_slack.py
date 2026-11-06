import io
import os
import unittest
import urllib.error
from contextlib import redirect_stdout
from unittest.mock import patch

from detector import DetectionResult
from slack import build_payload, post

SAMPLE_RESULT = DetectionResult(
    value=50.0,
    mean=10.1,
    stdev=0.663,
    z_score=60.2,
    expected_low=8.1,
    expected_high=12.1,
    is_anomaly=True,
)


class BuildPayloadTests(unittest.TestCase):
    def test_payload_includes_metric_value_range_and_action(self):
        payload = build_payload("CPUUtilization", SAMPLE_RESULT, "Scale the instance group.")
        text = str(payload)
        self.assertIn("CPUUtilization", text)
        self.assertIn("50.00", text)
        self.assertIn("8.10", text)
        self.assertIn("12.10", text)
        self.assertIn("Scale the instance group.", text)

    def test_payload_is_block_kit_shaped(self):
        payload = build_payload("CPUUtilization", SAMPLE_RESULT, "Scale the instance group.")
        self.assertIn("blocks", payload)
        self.assertTrue(all("type" in block for block in payload["blocks"]))


class PostTests(unittest.TestCase):
    def setUp(self):
        self.env_patch = patch.dict(os.environ, {}, clear=False)
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)

    def test_missing_webhook_env_warns_and_returns_false(self):
        os.environ.pop("SLACK_WEBHOOK_URL", None)
        buf = io.StringIO()
        with redirect_stdout(buf):
            result = post({"blocks": []})
        self.assertFalse(result)
        self.assertIn("SLACK_WEBHOOK_URL is not set", buf.getvalue())

    def test_successful_post_returns_true(self):
        os.environ["SLACK_WEBHOOK_URL"] = "https://hooks.example.com/services/T000/B000/xyz"

        class FakeResponse:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        with patch("slack.urllib.request.urlopen", return_value=FakeResponse()):
            result = post({"blocks": []})
        self.assertTrue(result)

    def test_http_error_warns_with_status_and_returns_false(self):
        os.environ["SLACK_WEBHOOK_URL"] = "https://hooks.example.com/services/T000/B000/xyz"
        error = urllib.error.HTTPError(
            url="https://hooks.example.com/x", code=404, msg="not found", hdrs=None, fp=None
        )
        buf = io.StringIO()
        with patch("slack.urllib.request.urlopen", side_effect=error):
            with redirect_stdout(buf):
                result = post({"blocks": []})
        self.assertFalse(result)
        self.assertIn("404", buf.getvalue())

    def test_connection_error_warns_and_returns_false(self):
        os.environ["SLACK_WEBHOOK_URL"] = "https://hooks.example.com/services/T000/B000/xyz"
        error = urllib.error.URLError("connection refused")
        buf = io.StringIO()
        with patch("slack.urllib.request.urlopen", side_effect=error):
            with redirect_stdout(buf):
                result = post({"blocks": []})
        self.assertFalse(result)
        self.assertIn("connection refused", buf.getvalue())

    def test_webhook_url_never_appears_in_output_even_on_failure(self):
        secret_url = "https://hooks.example.com/services/T000/B000/do-not-print-me"
        os.environ["SLACK_WEBHOOK_URL"] = secret_url
        error = urllib.error.URLError("boom")
        buf = io.StringIO()
        with patch("slack.urllib.request.urlopen", side_effect=error):
            with redirect_stdout(buf):
                post({"blocks": []})
        self.assertNotIn(secret_url, buf.getvalue())
        self.assertNotIn("do-not-print-me", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
