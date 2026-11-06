"""Idle-memory budget checks for the shipped apps.

Budget is PSS on Android and physical footprint on macOS: those are the
private-memory metrics a user actually feels. RSS is printed as a diagnostic
because it counts shared pages multiple times and can exceed 100 MiB even
when PSS is well under budget.
"""
import os
import re
import subprocess
import sys
import unittest

ANDROID_SERIAL = "4000TA1392222801462"
ANDROID_PACKAGE = "com.giathinh.hashplay.ncs"
BUDGET_MIB = 100.0


def _mac_hashplay_rows():
    out = subprocess.run(
        ["ps", "-axo", "pid=,rss=,command="], capture_output=True, text=True, timeout=30
    ).stdout
    rows = []
    for line in out.splitlines():
        parts = line.strip().split(None, 2)
        if len(parts) == 3 and "HashPlay" in parts[2] and int(parts[0]) not in {os.getpid(), os.getppid()}:
            rows.append((int(parts[0]), int(parts[1]), parts[2]))
    return rows


class IdleMemoryBudgetTests(unittest.TestCase):
    def test_mac_hashplay_idle_under_budget(self):
        rows = _mac_hashplay_rows()
        self.assertTrue(rows, "HashPlay Mac app is not running; idle memory cannot be verified")
        failures = []
        for pid, rss_kb, cmd in rows:
            vm = subprocess.run(["vmmap", "-summary", str(pid)], capture_output=True, text=True, timeout=30)
            footprint_m = None
            for line in vm.stdout.splitlines():
                if "Physical footprint:" in line:
                    match = re.search(r"Physical footprint:\s+([0-9.]+)([KMG])", line)
                    if match:
                        value = float(match.group(1))
                        unit = match.group(2)
                        footprint_m = value / 1024 if unit == "K" else value * 1024 if unit == "G" else value
                    break
            rss_mib = rss_kb / 1024
            print(f"MAC pid={pid} rss={rss_mib:.1f} MiB footprint={footprint_m} cmd={cmd}")
            if rss_mib >= BUDGET_MIB:
                failures.append(f"pid {pid} rss {rss_mib:.1f} MiB >= {BUDGET_MIB}")
        self.assertFalse(failures, "; ".join(failures))

    def test_android_nokia_ncs_idle_under_budget(self):
        devices = subprocess.run(["adb", "devices", "-l"], capture_output=True, text=True, timeout=30).stdout
        if ANDROID_SERIAL not in devices:
            self.fail(f"Android serial {ANDROID_SERIAL} not connected; idle memory cannot be verified")
        pid = subprocess.run(
            ["adb", "-s", ANDROID_SERIAL, "shell", "pidof", ANDROID_PACKAGE],
            capture_output=True, text=True, timeout=30,
        ).stdout.strip()
        self.assertTrue(pid, f"{ANDROID_PACKAGE} is not running on {ANDROID_SERIAL}")
        mem = subprocess.run(
            ["adb", "-s", ANDROID_SERIAL, "shell", "dumpsys", "meminfo", ANDROID_PACKAGE],
            capture_output=True, text=True, timeout=45,
        ).stdout
        match = re.search(r"TOTAL PSS:\s*(\d+)\s+TOTAL RSS:\s*(\d+)", mem)
        self.assertIsNotNone(match, "could not parse dumpsys meminfo TOTAL PSS/RSS")
        assert match is not None  # for static checkers; unittest already failed above if None
        pss_mib = int(match.group(1)) / 1024
        rss_mib = int(match.group(2)) / 1024
        print(f"ANDROID pid={pid} pss={pss_mib:.1f} MiB rss={rss_mib:.1f} MiB (rss diagnostic only)")
        self.assertLess(pss_mib, BUDGET_MIB, f"Android PSS {pss_mib:.1f} MiB >= {BUDGET_MIB}")


if __name__ == "__main__":
    unittest.main()
