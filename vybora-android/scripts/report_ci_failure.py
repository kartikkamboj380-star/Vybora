#!/usr/bin/env python3
"""Expose actionable CI log excerpts as GitHub Actions error annotations.

Artifacts retain the full logs. Annotations also make Gradle/compiler errors
readable through the Checks API when downloading the log archive is unavailable.
Only run this helper after a failed build; it never changes the build exit code.
"""

from pathlib import Path
import sys

MAX_MESSAGE_CHARS = 12_000


def escape_command(text: str) -> str:
    """Escape workflow-command data so log text cannot inject annotations."""
    return text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def diagnostic_excerpt(text: str) -> str:
    lines = text.splitlines()
    sections = []
    for index, line in enumerate(lines):
        if line.startswith("FAILURE:"):
            sections.append("Gradle failure:\n" + "\n".join(lines[index:index + 100]))
            break
    compiler_errors = [
        line for line in lines
        if line.startswith("e: ") or "error:" in line.lower()
        or "CMake Error" in line or "Could not resolve" in line
    ]
    if compiler_errors:
        sections.append("Compiler/dependency errors:\n" + "\n".join(compiler_errors[:60]))
    sections.append("Final log lines:\n" + "\n".join(lines[-60:]))
    message = "\n\n".join(sections)
    if len(message) > MAX_MESSAGE_CHARS:
        half = (MAX_MESSAGE_CHARS - 40) // 2
        message = message[:half] + "\n... full output in build logs ...\n" + message[-half:]
    return message


def main(paths: list[str]) -> None:
    for name in paths:
        path = Path(name)
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if text.strip():
            title = escape_command(f"CI failure details: {path.name}")
            print(f"::error title={title}::{escape_command(diagnostic_excerpt(text))}")


if __name__ == "__main__":
    main(sys.argv[1:])
