import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent


def get_secret_refs() -> set[str]:
    """Return all !secret <key> references found in keypad.yaml and keypad/*.yaml."""
    pattern = re.compile(r"!\s*secret\s+(\w+)")
    refs: set[str] = set()
    candidates = [ROOT / "keypad.yaml"] + list((ROOT / "keypad").glob("*.yaml"))
    for path in candidates:
        text = path.read_text(encoding="utf-8")
        refs.update(pattern.findall(text))
    return refs


def get_example_keys() -> set[str]:
    """Return the set of top-level keys defined in secrets.yaml.example."""
    example = ROOT / "secrets.yaml.example"
    keys: set[str] = set()
    for line in example.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and ":" in stripped:
            key = stripped.split(":")[0].strip()
            if key:
                keys.add(key)
    return keys


def test_secrets_example_covers_all_refs():
    """Every !secret ref in ESPHome YAML must have a key in secrets.yaml.example."""
    refs = get_secret_refs()
    keys = get_example_keys()
    missing = refs - keys
    assert not missing, (
        f"secrets.yaml.example is missing entries for: {sorted(missing)}\n"
        "Add a placeholder entry for each missing key so contributors know "
        "what to configure."
    )


def test_secrets_example_has_no_real_credentials():
    """secrets.yaml.example must not contain obvious real credentials."""
    example_text = (ROOT / "secrets.yaml.example").read_text(encoding="utf-8")
    # Reject lines that look like actual secrets (not placeholders / comments)
    suspicious_patterns = [
        # Real base64 key (44 chars, not containing REPLACE or placeholder words)
        r'^api_encryption_key:\s+"(?!REPLACE)[A-Za-z0-9+/]{43}="',
        # Real-looking WiFi password (longer than 8 chars, no placeholder words)
        r'^wifi_password:\s+"(?!Your|REPLACE|test|example|placeholder)\S{8,}"',
    ]
    for pattern in suspicious_patterns:
        assert not re.search(pattern, example_text, re.MULTILINE), (
            f"secrets.yaml.example may contain a real credential "
            f"(matched pattern: {pattern!r}). "
            "Use placeholder values only."
        )


def test_secrets_example_exists():
    """secrets.yaml.example must exist at the repo root."""
    assert (ROOT / "secrets.yaml.example").is_file(), (
        "secrets.yaml.example not found — it must be committed to the repo "
        "so new contributors know what secrets to configure."
    )


def test_secrets_yaml_is_gitignored():
    """secrets.yaml (the real file) must be listed in .gitignore."""
    gitignore = ROOT / ".gitignore"
    assert gitignore.is_file(), ".gitignore not found"
    text = gitignore.read_text(encoding="utf-8")
    # Accept /secrets.yaml or secrets.yaml
    assert re.search(r"/?secrets\.yaml\b", text), (
        "secrets.yaml must be listed in .gitignore to prevent accidental commit "
        "of real credentials."
    )


def test_keypad_yaml_packages_present():
    """keypad.yaml must include all required package files."""
    keypad_yaml = (ROOT / "keypad.yaml").read_text(encoding="utf-8")
    required_packages = ["board", "network", "fingerprint", "keypad", "status_light"]
    for pkg in required_packages:
        assert pkg in keypad_yaml, (
            f"keypad.yaml is missing the '{pkg}' package include. "
            "Check the packages: section."
        )


def test_all_included_package_files_exist():
    """Every !include target in keypad.yaml must point to an existing file."""
    keypad_yaml = (ROOT / "keypad.yaml").read_text(encoding="utf-8")
    # Match both   !include path  and  package: !include path
    includes = re.findall(r"!include\s+([\w/.\-]+\.yaml)", keypad_yaml)
    for rel_path in includes:
        target = ROOT / rel_path
        assert target.is_file(), (
            f"keypad.yaml includes '{rel_path}' but that file does not exist."
        )


def test_fingerprint_backup_header_exists():
    """fingerprint_backup.h must exist in the external component directory."""
    header = ROOT / "components" / "fingerprint_backup" / "fingerprint_backup.h"
    assert header.is_file(), (
        "components/fingerprint_backup/fingerprint_backup.h not found. "
        "This file is required for fingerprint backup/restore functionality."
    )
