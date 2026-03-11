from __future__ import annotations

import re
from pathlib import Path

DEV_ROOT = Path(__file__).resolve().parent.parent
BROKER_E2E_PATH = DEV_ROOT / "BROKER_E2E.md"
SECTION_RE = re.compile(r"^## (?P<title>.+)$", re.MULTILINE)


def load_sections(text: str) -> dict[str, str]:
    matches = list(SECTION_RE.finditer(text))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections[match.group("title")] = text[start:end]
    return sections


def assert_tokens(section: str, *, title: str, tokens: list[str]) -> None:
    missing = [token for token in tokens if token not in section]
    if missing:
        raise AssertionError(f"{title}: missing expected content: {', '.join(missing)}")


def main() -> None:
    sections = load_sections(BROKER_E2E_PATH.read_text())
    required_sections = {
        "Test A - Routing gate (`single`)": [
            'route="single"',
            "tiny, clear, low-risk",
            "Broker does not spawn any agents."
        ],
        "Test B - Routing gate (`multi`)": [
            'route="multi"',
            "ticket-dispatch/1",
            "authorized_skills",
            "Broker never writes repo content directly in `multi`."
        ],
        "Test C - Wait-any scheduling": [
            "wait-any",
            "warm workers",
            "write_scope"
        ],
        "Test D - Invalid-output recovery": [
            "one bounded retry",
            "closes the child",
            "salvage or redispatch"
        ],
        "Test E - Required review gates": [
            "spec_compliance",
            "code_quality",
            "ticket-result/1"
        ]
    }

    for title, tokens in required_sections.items():
        section = sections.get(title)
        if section is None:
            raise AssertionError(f"Missing section: {title}")
        assert_tokens(section, title=title, tokens=tokens)

    print("OK: BROKER_E2E covers single, multi, wait-any, recovery, and review gates")


if __name__ == "__main__":
    main()
