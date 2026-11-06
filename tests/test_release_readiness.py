"""Release-readiness checks for HashPlay v1.1.0.

These are deliberately small: they pin the facts that make a release
official instead of re-litigating every behavior test in the repo.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import updater  # noqa: E402


def test_version_is_stable_and_matches_release_notes():
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    assert version == "1.1.0", version
    assert "-rc" not in version
    notes = ROOT / "RELEASE_NOTES_v1.1.0.md"
    assert notes.exists(), f"missing {notes}"
    text = notes.read_text(encoding="utf-8")
    assert "1.1.0" in text
    assert "prerelease" not in text.lower()
    assert "do not treat this as a final release" not in text.lower()


def test_updater_points_at_current_github_repo():
    assert updater.REPO == "SimpleAppLauncher/NCS-SMLauncher", updater.REPO
    assert updater.API == "https://api.github.com/repos/{repo}/releases", updater.API


if __name__ == "__main__":
    test_version_is_stable_and_matches_release_notes()
    test_updater_points_at_current_github_repo()
    print("RELEASE READINESS PASSED")
