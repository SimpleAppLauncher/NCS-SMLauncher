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


def test_release_notes_do_not_hide_device_verification_status():
    text = (ROOT / "RELEASE_NOTES_v1.1.0.md").read_text(encoding="utf-8")
    lower = text.lower()
    assert "nokia t20" in lower, "release notes must name the device used for visual QA"
    assert "visual qa" in lower and "verified" in lower, "release notes must state visual QA status explicitly"
    assert "must be listed as pending" not in lower, "stale pending-visual-QA wording must be removed after device QA"


def test_no_stale_published_artifact_verifier():
    verifier = (ROOT / "scripts" / "verify_published_lite.py").read_text(encoding="utf-8")
    assert "Giathinh1234/NCS-SMLauncher" not in verifier, "stale old GitHub slug in published-artifact verifier"
    assert "v1.1.0-rc.4" not in verifier, "stale rc.4 tag in published-artifact verifier"
    assert "HashPlay-lite-macos-arm64.app.zip" in verifier, "published lite verifier must check the current lite asset name"


def test_shipped_scripts_have_no_old_repo_slug():
    shipped = list((ROOT / "src").glob("*.py")) + list((ROOT / "scripts").glob("*.py")) + list((ROOT / "tools").glob("*.py"))
    bad = []
    for path in shipped:
        if "Giathinh1234/NCS-SMLauncher" in path.read_text(encoding="utf-8", errors="replace"):
            bad.append(str(path.relative_to(ROOT)))
    assert not bad, f"old repo slug remains in shipped code/scripts: {bad}"


def test_release_notes_include_user_verification_steps():
    text = (ROOT / "RELEASE_NOTES_v1.1.0.md").read_text(encoding="utf-8")
    assert "SHA256" in text, "release notes must mention checksums"
    assert "shasum -a 256 -c SHA256SUMS.txt" in text, "release notes must give the exact checksum verification command"
    assert "SimpleAppLauncher/NCS-SMLauncher" in text, "release notes must link the current repo"


def test_every_src_module_is_named_by_a_behavior_test():
    test_text = "\n".join(
        p.read_text(encoding="utf-8", errors="replace")
        for p in (ROOT / "tests").glob("test_*.py")
    )
    missing = []
    for module in sorted((ROOT / "src").glob("*.py")):
        name = module.stem
        if name not in test_text:
            missing.append(name)
    assert not missing, f"src modules with no test naming them: {missing}"


if __name__ == "__main__":
    test_version_is_stable_and_matches_release_notes()
    test_updater_points_at_current_github_repo()
    test_release_notes_do_not_hide_device_verification_status()
    test_no_stale_published_artifact_verifier()
    test_shipped_scripts_have_no_old_repo_slug()
    test_release_notes_include_user_verification_steps()
    test_every_src_module_is_named_by_a_behavior_test()
    print("RELEASE READINESS PASSED")
