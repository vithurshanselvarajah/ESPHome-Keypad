#!/usr/bin/env python3

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

GITHUB_MODELS_URL = "https://models.inference.ai.azure.com/chat/completions"
MODEL = "gpt-4o"
MAX_DIFF_CHARS = 12_000
AI_TIMEOUT_SECS = 60

SYSTEM_PROMPT = """You are a technical writer generating release changelogs for an \
ESPHome firmware project. The project is an ESP32-S3 access controller with:
- 3×4 matrix keypad (key_collector, PIN entry, keypad_led_result script)
- R503 capacitive fingerprint sensor with aura LED ring (raw Grow UART backup/restore)
- WS2811 RGB LED strip, 4 LEDs (led_brightness_boost, saved-state globals)
- Full Home Assistant integration via encrypted API (events: keypad_code_entered,
  fingerprint_authenticated, fingerprint_backup_data; actions: set_led_colour,
  fingerprint_enroll, fingerprint_backup_slot, fingerprint_restore_slot)
- Optional debug mode (web server, standalone testing)
- Multi-keypad support via unique device_name substitutions

Write a structured Markdown changelog. Use exactly these sections (omit empty ones):
## Summary
## What's New
## Bug Fixes
## Breaking Changes
## Internal

Rules:
- Be specific — name actual scripts, entities, YAML files, and ESPHome components.
- Breaking Changes must be prominent and include migration steps if relevant.
- Check the release commit description carefully; the author may have listed
  important notes, breaking changes, or callouts there — these take precedence
  over your own analysis.
- Keep Summary to 2–3 sentences.
- Use bullet points within sections, not numbered lists."""


def git(*args: str, cwd: str = ".") -> str:
    result = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        cwd=cwd,
    )
    return result.stdout.strip()


def call_ai(token: str, prompt: str) -> str:
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 2048,
        "temperature": 0.3,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        GITHUB_MODELS_URL,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=AI_TIMEOUT_SECS) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result["choices"][0]["message"]["content"].strip()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {body[:400]}") from exc
    except (urllib.error.URLError, KeyError, json.JSONDecodeError) as exc:
        raise RuntimeError(str(exc)) from exc


def plain_changelog(    version: str,
    commit_subject: str,
    commit_body: str,
    commits: str,
) -> str:
    lines = [
        f"## Release {version}",
        "",
        f"_{commit_subject}_",
        "",
    ]
    if commit_body:
        lines += [commit_body, ""]
    lines.append("### Commits")
    for line in commits.splitlines():
        if line.strip():
            lines.append(f"- {line.strip()}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="AI-powered changelog generator")
    parser.add_argument("--version", required=True, help="Release version, e.g. 1.2.3")
    parser.add_argument("--from-ref", default="", help="Git ref of the previous release")
    parser.add_argument("--commit-subject", default="", help="Subject line of the release commit")
    parser.add_argument(
        "--commit-body-file",
        default="",
        help="Path to a file containing the release commit body (may include breaking change notes)",
    )
    parser.add_argument("--output", default="", help="Write changelog to this file (stdout if omitted)")
    parser.add_argument("--repo-path", default=".", help="Path to the git repository root")
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN", "")

    commit_body = ""
    if args.commit_body_file:
        body_path = Path(args.commit_body_file)
        if body_path.is_file():
            commit_body = body_path.read_text(encoding="utf-8").strip()

    if args.from_ref:
        rev_range = f"{args.from_ref}..HEAD"
        diff_ref = args.from_ref
    else:
        rev_range = None
        diff_ref = None

    commits = (
        git("log", rev_range, "--pretty=format:%h %s (%an)", cwd=args.repo_path)
        if rev_range
        else git("log", "--pretty=format:%h %s (%an)", cwd=args.repo_path)
    )
    commits = commits or "(no commits found)"

    if diff_ref:
        diff_stat = git("diff", f"{diff_ref}..HEAD", "--stat", cwd=args.repo_path)
        diff = git("diff", f"{diff_ref}..HEAD", "--unified=2", cwd=args.repo_path)
        if len(diff) > MAX_DIFF_CHARS:
            diff = diff[:MAX_DIFF_CHARS] + "\n\n[diff truncated — showing first 12 000 chars]"
    else:
        diff_stat = "(initial release — no previous version to diff against)"
        diff = ""

    prompt_parts = [
        f"Generate a changelog for version {args.version}.",
        f"\nRelease commit subject: {args.commit_subject}",
    ]
    if commit_body:
        prompt_parts.append(
            "\nRelease commit description (author-supplied — check for breaking "
            f"changes and migration notes):\n{commit_body}"
        )
    prompt_parts += [
        f"\nCommits included in this release:\n{commits}",
        f"\nChanged files (diff --stat):\n{diff_stat}",
    ]
    if diff:
        prompt_parts.append(f"\nFull diff (--unified=2):\n{diff}")

    prompt = "\n".join(prompt_parts)

    changelog = ""
    if token:
        try:
            changelog = call_ai(token, prompt)
            print("AI changelog generated successfully.", file=sys.stderr)
        except RuntimeError as exc:
            print(f"::warning::AI changelog failed: {exc} — using git-log fallback.", file=sys.stderr)
    else:
        print("::warning::GITHUB_TOKEN not set — using git-log fallback.", file=sys.stderr)

    if not changelog:
        changelog = plain_changelog(args.version, args.commit_subject, commit_body, commits)

    if args.output:
        Path(args.output).write_text(changelog, encoding="utf-8")
        print(f"Changelog written to {args.output}", file=sys.stderr)
    else:
        print(changelog)


if __name__ == "__main__":
    main()
