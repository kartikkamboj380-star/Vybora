#!/usr/bin/env python3
"""Fail fast when the Android archive lacks referenced images, fonts, or resources.

Audit project-owned file/value resources referenced by source XML and Kotlin R
lookups across the Android modules. Framework-qualified resources, generated IDs,
attributes, and dependency-provided XML styles are intentionally excluded. This
is a preflight check, not a replacement for Android's resource linker/compiler.
"""

from collections import defaultdict
from pathlib import Path
import re
import xml.etree.ElementTree as ET

PROJECT = Path(__file__).resolve().parents[1]
XML_REFERENCE = re.compile(
    r"@(drawable|mipmap|font|raw|color|xml|anim|animator|layout|menu|string|plurals|array|integer|bool|dimen)/([\w.]+)"
)
KOTLIN_REFERENCE = re.compile(r"(?<![\w.])R\.(\w+)\.(\w+)")


def declared_resources(project=PROJECT):
    resources = set()
    for resource_root in project.glob("*/src/*/res"):
        for directory in resource_root.iterdir():
            if not directory.is_dir():
                continue
            kind = directory.name.split("-", 1)[0]
            for path in directory.iterdir():
                if not path.is_file():
                    continue
                if kind == "values" and path.suffix == ".xml":
                    for item in ET.parse(path).getroot():
                        name = item.get("name")
                        if not name:
                            continue
                        resource_type = item.get("type") if item.tag == "item" else item.tag
                        resource_type = {"string-array": "array", "integer-array": "array"}.get(resource_type, resource_type)
                        resources.add((resource_type, name.replace(".", "_") if resource_type == "style" else name))
                else:
                    resources.add((kind, path.name.split(".", 1)[0]))
    return resources


def missing_resources(project=PROJECT):
    declared = declared_resources(project)
    missing = defaultdict(set)
    for source_root in project.glob("*/src"):
        for path in source_root.rglob("*"):
            if not path.is_file() or path.suffix not in (".xml", ".kt", ".kts"):
                continue
            if "test" in path.parts or "androidTest" in path.parts:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            references = set(KOTLIN_REFERENCE.findall(text))
            if path.suffix == ".xml":
                references.update(XML_REFERENCE.findall(text))
            for kind, name in references:
                if kind not in ("id", "attr", "styleable") and (kind, name) not in declared:
                    missing[(kind, name)].add(path.relative_to(project).as_posix())
    return missing


if __name__ == "__main__":
    missing = missing_resources()
    for (kind, name), paths in sorted(missing.items()):
        print(f"Missing {kind}/{name}: {', '.join(sorted(paths)[:3])}")
    if missing:
        raise SystemExit(1)
    print("All project-owned XML/Kotlin resource references have definitions.")
