import unittest
from unittest.mock import patch, MagicMock
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from api_monitor import check_target

class TestApiMonitor(unittest.TestCase):

    @patch('api_monitor.request_once')
    def test_check_target_success(self, mock_request):
        mock_request.return_value = 200

        target = {
            "name": "Test Endpoint",
            "url": "http://example.com",
            "expected_status": 200,
            "timeout_seconds": 5,
            "slow_threshold_seconds": 2.0
        }

        result = check_target(target, "2026-11-03T20:00:00Z")
        self.assertEqual(result['status'], 'healthy')
        self.assertIsNone(result['failure_type'])

    @patch('api_monitor.request_once')
    def test_check_target_unexpected_code(self, mock_request):
        mock_request.return_value = 404

        target = {
            "name": "Test Endpoint 404",
            "url": "http://example.com/404",
            "expected_status": 200,
            "timeout_seconds": 5,
            "slow_threshold_seconds": 2.0
        }

        result = check_target(target, "2026-11-03T20:00:00Z")
        self.assertEqual(result['status'], 'problem')
        self.assertEqual(result['failure_type'], 'unexpected_status')

if __name__ == '__main__':
    unittest.main()