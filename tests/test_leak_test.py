"""Tests for leak_test.py helpers, with the network and osascript mocked."""
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import requests  # noqa: E402

import leak_test  # noqa: E402


class FakeResponse:
    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        return None


class GetPublicIpTest(unittest.TestCase):
    def test_valid_ip_is_stripped_and_returned(self):
        with mock.patch.object(leak_test.requests, "get", return_value=FakeResponse(" 203.0.113.7\n")):
            self.assertEqual(leak_test.get_public_ip(), "203.0.113.7")

    def test_non_ip_response_returns_none(self):
        with mock.patch.object(leak_test.requests, "get", return_value=FakeResponse("<html>error</html>")):
            self.assertIsNone(leak_test.get_public_ip())

    def test_request_failure_returns_none(self):
        with mock.patch.object(
            leak_test.requests, "get", side_effect=requests.exceptions.ConnectionError("down")
        ):
            self.assertIsNone(leak_test.get_public_ip())

    def test_timeout_is_two_seconds(self):
        with mock.patch.object(leak_test.requests, "get", return_value=FakeResponse("198.51.100.2")) as get:
            leak_test.get_public_ip()
        self.assertEqual(get.call_args.kwargs.get("timeout"), 2)


class GetLocalIpTest(unittest.TestCase):
    def test_hostname_resolution(self):
        with mock.patch.object(leak_test.socket, "gethostname", return_value="mac"), \
                mock.patch.object(leak_test.socket, "gethostbyname", return_value="192.168.1.5"):
            self.assertEqual(leak_test.get_local_ip(), "192.168.1.5")

    def test_resolution_failure_returns_none(self):
        with mock.patch.object(leak_test.socket, "gethostname", return_value="mac"), \
                mock.patch.object(leak_test.socket, "gethostbyname", side_effect=leak_test.socket.gaierror):
            self.assertIsNone(leak_test.get_local_ip())


class NotifyTest(unittest.TestCase):
    def test_notify_calls_osascript_with_built_string(self):
        with mock.patch.object(leak_test.subprocess, "run") as run:
            leak_test.notify("Title", "Body text", "Sosumi")
        args = run.call_args.args[0]
        self.assertEqual(args[:2], ["osascript", "-e"])
        self.assertIn('display notification "Body text" with title "Title"', args[2])
        self.assertFalse(run.call_args.kwargs["check"])


class EntryPointTest(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(ROOT / "leak_test.py"), *args],
            capture_output=True, text=True, timeout=15,
        )

    def test_help_exits_zero(self):
        result = self.run_cli("--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn("Usage:", result.stdout)

    def test_unknown_argument_exits_two(self):
        result = self.run_cli("--bogus")
        self.assertEqual(result.returncode, 2)
        self.assertIn("unknown argument", result.stderr)


if __name__ == "__main__":
    unittest.main()
