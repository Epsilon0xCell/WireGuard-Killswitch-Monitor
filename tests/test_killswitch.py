"""Stub-driven tests for killswitch.sh.

This host is Linux, so pfctl, ifconfig, netstat, wg, sudo, and sleep
are replaced with small shell stubs on PATH and the real script runs
against them. That verifies the script control flow and the ruleset
text it writes. It does not verify real pf behavior on macOS.
"""
import os
import signal
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "killswitch.sh"

STUBS = {
    "sudo": '#!/bin/sh\nexec "$@"\n',
    "pfctl": (
        '#!/bin/sh\n'
        'echo "pfctl $@" >> "$PFCTL_LOG"\n'
        'if [ "$1" = "-f" ]; then cat "$2" >> "$PFCTL_LOG"; '
        'if [ -n "$PFCTL_FAIL_F" ]; then echo "pfctl: syntax error" >&2; exit 1; fi; fi\n'
        'if [ "$1" = "-E" ] && [ -n "$PFCTL_FAIL_E" ]; then echo "pfctl: cannot enable" >&2; exit 1; fi\n'
        'exit 0\n'
    ),
    "ifconfig": (
        '#!/bin/sh\n'
        'if [ -n "$FAKE_IFACE_DOWN" ] && [ "$1" != "-a" ]; then exit 1; fi\n'
        'echo "utun4: flags=8051<UP,POINTOPOINT,RUNNING,MULTICAST> mtu ${FAKE_MTU:-1280}"\n'
        'echo "\tinet 10.0.0.2 --> 10.0.0.2 netmask 0xffffffff"\n'
    ),
    "netstat": '#!/bin/sh\necho "udp4 0 0 *.51820 *.*"\n',
    "wg": '#!/bin/sh\nexit 0\n',
    "sleep": '#!/bin/sh\nexec /bin/sleep 0.05\n',
}


class KillswitchTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.bin = Path(self.tmp.name) / "bin"
        self.bin.mkdir()
        for name, body in STUBS.items():
            path = self.bin / name
            path.write_text(body)
            path.chmod(0o755)
        self.log = Path(self.tmp.name) / "pfctl.log"
        self.log.write_text("")

    def env(self, **extra):
        env = dict(os.environ)
        env["PATH"] = f"{self.bin}:{env['PATH']}"
        env["PFCTL_LOG"] = str(self.log)
        env.update(extra)
        return env

    def run_script(self, args, env_extra=None, run_seconds=1.2):
        proc = subprocess.Popen(
            ["bash", str(SCRIPT), *args],
            env=self.env(**(env_extra or {})),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        )
        time.sleep(run_seconds)
        if proc.poll() is None:
            proc.send_signal(signal.SIGTERM)
        out, _ = proc.communicate(timeout=10)
        return proc.returncode, out

    def run_quick(self, args, env_extra=None):
        result = subprocess.run(
            ["bash", str(SCRIPT), *args],
            env=self.env(**(env_extra or {})),
            capture_output=True, text=True, timeout=10,
        )
        return result.returncode, result.stdout + result.stderr

    def test_syntax(self):
        result = subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True)
        self.assertEqual(result.returncode, 0)

    def test_help_exits_zero_without_touching_pf(self):
        code, out = self.run_quick(["--help"])
        self.assertEqual(code, 0)
        self.assertIn("Usage:", out)
        self.assertEqual(self.log.read_text(), "")

    def test_unknown_argument_exits_two_without_touching_pf(self):
        code, out = self.run_quick(["--bogus"])
        self.assertEqual(code, 2)
        self.assertIn("unknown argument", out)
        self.assertEqual(self.log.read_text(), "")

    def test_bad_ports_exit_two_without_touching_pf(self):
        for bad in ("abc", "0", "70000", "51820;evil", ""):
            if bad == "":
                continue
            code, out = self.run_quick([], {"WIREGUARD_PORT": bad})
            self.assertEqual(code, 2, bad)
            self.assertIn("invalid WIREGUARD_PORT", out)
        self.assertEqual(self.log.read_text(), "")

    def test_bad_interface_name_exits_two_without_touching_pf(self):
        code, out = self.run_quick([], {"VPN_INTERFACE": "utun4\npass all"})
        self.assertEqual(code, 2)
        self.assertIn("invalid VPN interface name", out)
        self.assertEqual(self.log.read_text(), "")

    def test_connected_loads_one_ruleset_with_all_three_rules(self):
        code, out = self.run_script([])
        log = self.log.read_text()
        self.assertEqual(code, 0)
        self.assertIn("VPN is connected on utun4. Allowing traffic.", out)
        self.assertEqual(log.count("pfctl -f"), 1)
        self.assertIn("block all\npass in on utun4 all\npass out on utun4 all", log)
        self.assertIn("pfctl -F all", log)
        self.assertIn("pfctl -d", log)
        self.assertIn("Kill switch disabled. Internet access restored.", out)

    def test_failed_load_is_reported_and_retried_not_believed(self):
        code, out = self.run_script([], {"PFCTL_FAIL_F": "1"})
        self.assertGreaterEqual(self.log.read_text().count("pfctl -f"), 2)
        self.assertNotIn("Allowing traffic.", out)
        self.assertIn("pfctl failed to load the ruleset", out)

    def test_pf_enable_failure_exits_one(self):
        code, out = self.run_quick([], {"PFCTL_FAIL_E": "1"})
        self.assertEqual(code, 1)
        self.assertIn("Killswitch is NOT active", out)

    def test_down_interface_loads_block_only(self):
        code, out = self.run_script([], {"FAKE_IFACE_DOWN": "1"})
        log = self.log.read_text()
        self.assertIn("VPN is disconnected. Enforcing killswitch.", out)
        self.assertIn("block all", log)
        self.assertNotIn("pass in on", log)


if __name__ == "__main__":
    unittest.main()
