#!/usr/bin/env python3

import json
import os
import subprocess
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
WRAPPER = REPO_ROOT / "research-pro" / "scripts" / "agent-browser-node.sh"


def run(cmd, cwd: Path, *, check: bool = True, env=None) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        check=False,
        text=True,
        capture_output=True,
        env=env,
    )
    if check and proc.returncode != 0:
        cmd_text = " ".join(cmd)
        raise AssertionError(
            f"command failed: {cmd_text}\n"
            f"cwd: {cwd}\n"
            f"stdout:\n{proc.stdout}\n"
            f"stderr:\n{proc.stderr}"
        )
    return proc


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def assert_equal(actual, expected, message: str) -> None:
    if actual != expected:
        raise AssertionError(f"{message}: expected {expected!r}, got {actual!r}")


def assert_in(needle: str, haystack: str, message: str) -> None:
    if needle not in haystack:
        raise AssertionError(f"{message}: missing {needle!r}\n--- output ---\n{haystack}")


def main() -> None:
    no_args = run(["bash", str(WRAPPER)], cwd=REPO_ROOT, check=False)
    assert_equal(no_args.returncode, 64, "wrapper should fail fast without args")
    assert_in("Usage:", no_args.stderr, "wrapper should print usage on stderr")
    print("OK: wrapper rejects missing args with usage guidance")

    with tempfile.TemporaryDirectory(prefix="research-pro-smoke-") as tmp_dir:
        temp_root = Path(tmp_dir)
        fake_js = temp_root / "fake-agent-browser.js"
        write_text(
            fake_js,
            "console.log(JSON.stringify(process.argv.slice(2)));\n",
        )

        env = os.environ.copy()
        env["AGENT_BROWSER_JS_PATH"] = str(fake_js)
        passthrough = run(
            ["bash", str(WRAPPER), "open", "https://chatgpt.com", "--session", "research-pro"],
            cwd=REPO_ROOT,
            env=env,
        )
        forwarded = json.loads(passthrough.stdout.strip())
        assert_equal(
            forwarded,
            ["open", "https://chatgpt.com", "--session", "research-pro"],
            "wrapper should forward args unchanged",
        )
        print("OK: wrapper forwards args unchanged when AGENT_BROWSER_JS_PATH is set")


if __name__ == "__main__":
    main()
