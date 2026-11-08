#!/usr/bin/env python3
"""Expose actionable CI log excerpts as GitHub Actions error annotations.

Artifacts retain the full logs. Annotations also make Gradle/compiler errors
readable through the Checks API when downloading the log archive is unavailable.
Only run this helper after a failed build; it never changes the build exit code.
"""

from pathlib import Path
import sys

MAX_MESSAGE_CHARS = 12_000
# Keep each annotation below the 4,096-character API message limit.
ANNOTATION_CHARS = 3_500


def escape_command(text: str) -> str:
    """Escape workflow-command data so log text cannot inject annotations."""
    return text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def diagnostic_excerpt(text: str) -> str:
    lines = text.splitlines()
    sections = []
    # Gradle may report multiple failures separated by very long stacktraces.
    # Retain every "What went wrong" summary, not just the first exception.
    for index, line in enumerate(lines):
        if line.strip() == "* What went wrong:":
            summary = []
            for following in lines[index + 1:index + 81]:
                if following.startswith(("* Try:", "* Exception is:", "\tat ", "====")):
                    break
                summary.append(following)
            sections.append("Gradle failure:\n" + "\n".join(summary).strip())
    compiler_errors = list(dict.fromkeys(
        line for line in lines
        if line.startswith("e: ") or "error:" in line.lower()
        or "CMake Error" in line or "Could not resolve" in line
    ))
    if compiler_errors:
        sections.append("Compiler/dependency errors:\n" + "\n".join(compiler_errors[:60]))
    sections.append("Final log lines:\n" + "\n".join(lines[-40:]))
    message = "\n\n".join(sections)
    if len(message) > MAX_MESSAGE_CHARS:
        half = (MAX_MESSAGE_CHARS - 40) // 2
        message = message[:half] + "\n... full output in build logs ...\n" + message[-half:]
    return message


def main(paths: list[str]) -> None:
    # Paths are supplied in execution order. Only the last nonempty log belongs
    # to the failed stage; do not label successful SDK/license output as errors.
    for name in reversed(paths):
        path = Path(name)
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if not text.strip():
            continue
        message = diagnostic_excerpt(text)
        chunks = [message[index:index + ANNOTATION_CHARS]
                  for index in range(0, len(message), ANNOTATION_CHARS)]
        for index, chunk in enumerate(chunks, 1):
            suffix = f" [{index}/{len(chunks)}]" if len(chunks) > 1 else ""
            title = escape_command(f"CI failure details: {path.name}{suffix}")
            print(f"::error title={title}::{escape_command(chunk)}")
        break


if __name__ == "__main__":
    main(sys.argv[1:])
