import unittest

from detector import detect


class DetectorTests(unittest.TestCase):
    def test_spike_is_detected(self):
        window = [10.0, 11.0, 9.0, 10.0, 10.5, 50.0]
        result = detect(window, threshold=3.0)
        self.assertTrue(result.is_anomaly)
        self.assertEqual(result.value, 50.0)

    def test_flat_series_with_small_move_is_not_anomaly(self):
        window = [10.0, 10.1, 9.9, 10.0, 10.2, 10.1]
        result = detect(window, threshold=3.0)
        self.assertFalse(result.is_anomaly)

    def test_noisy_series_within_threshold_is_not_anomaly(self):
        window = [10.0, 14.0, 6.0, 12.0, 8.0, 13.0]
        result = detect(window, threshold=3.0)
        self.assertFalse(result.is_anomaly)

    def test_noisy_series_can_still_flag_a_real_outlier(self):
        window = [10.0, 14.0, 6.0, 12.0, 8.0, 100.0]
        result = detect(window, threshold=3.0)
        self.assertTrue(result.is_anomaly)

    def test_too_few_points_is_not_an_anomaly(self):
        result = detect([5.0, 6.0], threshold=3.0)
        self.assertFalse(result.is_anomaly)
        self.assertEqual(result.value, 6.0)

    def test_empty_window_is_not_an_anomaly(self):
        result = detect([], threshold=3.0)
        self.assertFalse(result.is_anomaly)
        self.assertEqual(result.value, 0.0)

    def test_zero_variance_unchanged_value_is_not_anomaly(self):
        window = [5.0, 5.0, 5.0, 5.0]
        result = detect(window, threshold=3.0)
        self.assertFalse(result.is_anomaly)
        self.assertEqual(result.stdev, 0.0)

    def test_zero_variance_changed_value_is_anomaly(self):
        window = [5.0, 5.0, 5.0, 9.0]
        result = detect(window, threshold=3.0)
        self.assertTrue(result.is_anomaly)
        self.assertEqual(result.stdev, 0.0)

    def test_expected_range_is_centered_on_mean(self):
        window = [10.0, 10.0, 10.0, 10.0]
        result = detect(window, threshold=2.0)
        self.assertEqual(result.mean, 10.0)


if __name__ == "__main__":
    unittest.main()
