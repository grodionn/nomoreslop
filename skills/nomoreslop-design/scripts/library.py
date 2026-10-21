#!/usr/bin/env python3
"""Read selected design records and validate the self-contained library.

Only build-index writes files. All other commands are read-only.
Third-party packages are optional and only used by stats for token counting.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
REFERENCES = ROOT / "references"
CORE_CHAR_BUDGET = 20_000
START_IDS = (
    "TXT-01", "TXT-03", "TXT-04", "TXT-08", "TXT-11", "TXT-37",
    "LAY-11", "LAY-17", "LAY-18", "LAY-19", "TYP-02", "TYP-09", "TYP-14",
    "CTL-13", "CTL-14", "CTL-15", "CTL-16",
    "IMG-09", "MOT-13", "MOT-14", "PRC-10", "PRC-11", "PRC-12", "PRC-15", "PRC-16",
)
START_STAGES = {
    "content": (
        "TXT-01", "TXT-03", "TXT-04", "TXT-08", "TXT-11", "TXT-37",
        "LAY-18", "PRC-12", "PRC-16",
    ),
    "composition": (
        "LAY-11", "LAY-17", "LAY-19", "TYP-02", "TYP-09", "TYP-14",
        "IMG-09", "PRC-10", "PRC-15",
    ),
    "detail": ("CTL-13", "CTL-14", "CTL-15", "CTL-16", "MOT-13", "MOT-14", "PRC-11"),
}
GROUPS = (
    ("antipattern", "TXT", "Текст", "antipatterns/text.md"),
    ("antipattern", "LAY", "Композиция", "antipatterns/layout.md"),
    ("antipattern", "TYP", "Типографика", "antipatterns/typography.md"),
    ("antipattern", "COL", "Цвет и материал", "antipatterns/color-material.md"),
    ("antipattern", "CTL", "Управление", "antipatterns/controls.md"),
    ("antipattern", "MOT", "Движение", "antipatterns/motion.md"),
    ("antipattern", "IMG", "Изображения", "antipatterns/imagery.md"),
    ("antipattern", "PAG", "Типы страниц", "antipatterns/pages.md"),
    ("antipattern", "PRC", "Процесс", "antipatterns/process.md"),
    ("technique", "CMP", "Композиционные приёмы", "techniques/composition.md"),
    ("technique", "MAT", "Типографика и материалы", "techniques/type-material.md"),
    ("technique", "BG", "Изображения и фон", "techniques/imagery-background.md"),
    ("technique", "FX", "Движение", "techniques/motion.md"),
    ("technique", "UX", "Взаимодействие", "techniques/interaction.md"),
)
HEADING = re.compile(r"^### ([A-Z]+-\d{2}) — (.+?)(?: \[([ДКУ])\])?[ \t]*$", re.M)
LINK = re.compile(r"!?\[[^\]\n]*\]\((<?[^)\s]+>?)\)")
ID_REFERENCE = re.compile(r"(?<![A-Z0-9])([A-Z]{2,4}-\d{2})(?!\d)")


@dataclass(frozen=True)
class Record:
    identifier: str
    title: str
    status: str | None
    kind: str
    source: Path
    body: str

    def render(self) -> str:
        status = f" [{self.status}]" if self.status else ""
        return f"### {self.identifier} — {self.title}{status}\n\n{self.body}\n"


def load_records() -> list[Record]:
    records = []
    seen = set()
    for kind, prefix, _label, relative in GROUPS:
        source = REFERENCES / relative
        content = source.read_text(encoding="utf-8")
        headings = list(HEADING.finditer(content))
        raw_headings = re.findall(r"^### .+$", content, re.M)
        if not headings or len(headings) != len(raw_headings):
            raise ValueError(f"Missing or malformed record heading: {relative}")
        for number, heading in enumerate(headings, start=1):
            identifier, title, status = heading.groups()
            if identifier in seen:
                raise ValueError(f"Duplicate identifier: {identifier}")
            expected = f"{prefix}-{number:02}"
            if identifier != expected:
                raise ValueError(f"Expected {expected}, found {identifier}: {relative}")
            if (kind == "antipattern" and status is None) or (
                kind == "technique" and status is not None
            ):
                raise ValueError(f"Invalid status for {identifier}")
            end = headings[number].start() if number < len(headings) else len(content)
            body = content[heading.end():end].strip()
            labels = (
                ("Сигнал:", "Действие:", "Граница:", "Пример:")
                if kind == "antipattern"
                else ("Вид:", "Когда:", "Учти:")
            )
            lines = body.splitlines()
            for label in labels:
                matches = [line for line in lines if line.startswith(label)]
                if len(matches) != 1 or not matches[0][len(label):].strip():
                    raise ValueError(f"Missing, empty or repeated {label} in {identifier}")
            records.append(Record(identifier, title, status, kind, source, body))
            seen.add(identifier)
    return records


def render_index(records: list[Record], kind: str) -> str:
    if kind == "antipattern":
        lines = [
            "# Индекс антипаттернов",
            "",
            "Открывай для поиска дополнительных записей по текущему этапу. Название — короткий симптом, полные условия находятся в записи.",
            "",
            "**Д** — исключено из автоматического выбора; **К** — контекстный сигнал; **У** — ошибка при описанных условиях. Явное задание и авторский материал учитываются. Это каталог решений, а не детектор авторства.",
            "",
            "Для нового UI загружай подробные правила по этапам: python <путь-к-скиллу>/scripts/library.py start --stage content, затем --stage composition, затем --stage detail. Порядок работы и ID для чтения без Python указаны в [поэтапном процессе](staged-workflow.md). Дополнения: python <путь-к-скиллу>/scripts/library.py show TXT-01 LAY-01. Не загружай все разделы заранее.",
        ]
        filename = "antipattern-index.md"
    else:
        lines = [
            "# Индекс дизайн-приёмов",
            "",
            "Открывай при выборе направления или подходящего выразительного средства. Сначала выбери семейство по задаче, затем прочитай несколько нужных записей. Применять всё перечисленное не требуется.",
            "",
            "Записи объясняют вид, применение и ограничение в трёх коротких предложениях. Человеку представляй только подходящие варианты; термин поясняй простым языком.",
            "",
            "Выборочное чтение: python <путь-к-скиллу>/scripts/library.py show MAT-01 FX-01. Поддержку технологий и ресурсы конкретного проекта проверяй при реализации.",
        ]
        filename = "technique-index.md"
    for group_kind, prefix, label, relative in GROUPS:
        if group_kind != kind:
            continue
        group_records = [r for r in records if r.identifier.startswith(prefix + "-")]
        lines.extend(("", f"## [{label}]({relative})", ""))
        for record in group_records:
            status = f" [{record.status}]" if record.status else ""
            lines.append(f"- {record.identifier} {record.title}{status}")
    lines.extend(("", f"Индекс обновляется из записей командой scripts/library.py build-index; файл: {filename}.", ""))
    return "\n".join(lines)


def markdown_files() -> list[Path]:
    return sorted(ROOT.rglob("*.md"))


def validate(records: list[Record]) -> list[str]:
    errors = []
    identifiers = {r.identifier for r in records}
    for identifier in START_IDS:
        if identifier not in identifiers:
            errors.append(f"Missing startup record: {identifier}")
    for kind, filename in (
        ("antipattern", "antipattern-index.md"),
        ("technique", "technique-index.md"),
    ):
        path = REFERENCES / filename
        if not path.is_file() or path.read_text(encoding="utf-8") != render_index(records, kind):
            errors.append(f"Missing or stale index: references/{filename}; run build-index")
    for source in markdown_files():
        text = source.read_text(encoding="utf-8")
        boundary = ROOT
        for match in LINK.finditer(text):
            link = match.group(1).strip("<>")
            parsed = urlsplit(link)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            destination = (source.parent / unquote(parsed.path)).resolve()
            if not destination.is_relative_to(boundary):
                errors.append(f"Link escapes package: {source.name}: {link}")
            elif not destination.is_file():
                errors.append(f"Broken local link: {source.name}: {link}")
        for identifier in sorted(set(ID_REFERENCE.findall(text)) - identifiers):
            errors.append(f"Unknown record reference: {source.name}: {identifier}")
        if "[TODO:" in text or "\ufffd" in text:
            errors.append(f"Unfinished scaffold or replacement character: {source.name}")
    skill_path = ROOT / "SKILL.md"
    core = skill_path.read_text(encoding="utf-8")
    if not re.match(r"\A---\nname: nomoreslop-design\ndescription: .+\n---\n", core):
        errors.append("Invalid or unexpected SKILL.md frontmatter")
    index = REFERENCES / "antipattern-index.md"
    if index.is_file():
        core_chars = len(core) + len(index.read_text(encoding="utf-8"))
        if core_chars > CORE_CHAR_BUDGET:
            errors.append(f"Core exceeds character budget: {core_chars} > {CORE_CHAR_BUDGET}")
    for image in (REFERENCES / "examples").glob("*.png"):
        with image.open("rb") as stream:
            if stream.read(8) != b"\x89PNG\r\n\x1a\n":
                errors.append(f"Invalid PNG: {image.name}")
    return errors


def measure(text: str, encoding) -> dict:
    result = {"characters": len(text), "utf8_bytes": len(text.encode("utf-8"))}
    if encoding is not None:
        result["tokens"] = len(encoding.encode(text))
    return result


def show_stats(records: list[Record], encoding_name: str | None) -> None:
    encoding = None
    tokenizer_note = "No token count requested; characters and bytes are not tokens."
    if encoding_name:
        try:
            import tiktoken
        except ImportError as error:
            raise ValueError("Token counting requires optional tiktoken; no estimates substituted.") from error
        encoding = tiktoken.get_encoding(encoding_name)
        tokenizer_note = "Reference encoding only; actual model and tool overhead may differ."
    per_file = {}
    for source in sorted(ROOT.rglob("*.md")):
        per_file[source.relative_to(ROOT).as_posix()] = measure(
            source.read_text(encoding="utf-8"), encoding
        )
    core = "\n".join(
        (ROOT / path).read_text(encoding="utf-8")
        for path in ("SKILL.md", "references/antipattern-index.md")
    )
    lookup = {record.identifier: record for record in records}

    def selected(*identifiers):
        return "\n".join(lookup[identifier].render() for identifier in identifiers)

    packets = {
        "core": core,
        "new_ui_start": core + selected(*START_IDS),
        "new_ui_brief": core + selected(*START_IDS)
        + (REFERENCES / "brief-and-decisions.md").read_text(encoding="utf-8"),
        "art_direction_example": core + selected(*START_IDS)
        + (REFERENCES / "art-direction.md").read_text(encoding="utf-8")
        + selected("CMP-06", "CMP-11", "FX-10", "BG-04"),
        "redesign_brief_example": core + selected(*START_IDS)
        + (REFERENCES / "brief-and-decisions.md").read_text(encoding="utf-8")
        + (REFERENCES / "redesign-workflow.md").read_text(encoding="utf-8")
        + selected("PRC-13", "PRC-14", "IMG-11"),
        "brand_assets_example": core
        + (REFERENCES / "brand-assets.md").read_text(encoding="utf-8")
        + selected("IMG-10"),
        "copy_edit_example": core
        + (REFERENCES / "content-workflow.md").read_text(encoding="utf-8")
        + selected("TXT-01", "TXT-03", "TXT-07", "TXT-09", "TXT-11", "TXT-28"),
        "font_research_example": core
        + (REFERENCES / "font-research.md").read_text(encoding="utf-8")
        + selected("TYP-01", "TYP-02", "TYP-03", "TYP-11"),
        "motion_selection_example": core
        + (REFERENCES / "technique-index.md").read_text(encoding="utf-8")
        + selected("FX-01", "FX-03", "FX-10", "MOT-09"),
    }
    entry = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    workflow = (REFERENCES / "staged-workflow.md").read_text(encoding="utf-8")
    for stage, identifiers in START_STAGES.items():
        packets[f"{stage}_stage"] = entry + workflow + selected(*identifiers)
    all_markdown = "\n".join(
        source.read_text(encoding="utf-8") for source in sorted(ROOT.rglob("*.md"))
    )
    print(json.dumps({
        "antipatterns": sum(r.kind == "antipattern" for r in records),
        "techniques": sum(r.kind == "technique" for r in records),
        "encoding": encoding_name,
        "note": tokenizer_note,
        "core_character_budget": CORE_CHAR_BUDGET,
        "packets": {name: measure(text, encoding) for name, text in packets.items()},
        "all_markdown": measure(all_markdown, encoding),
        "per_file": per_file,
    }, ensure_ascii=False, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    start = commands.add_parser("start", help="Print baseline records, optionally limited to the current stage")
    start.add_argument("--stage", choices=tuple(START_STAGES), help="Load only the current stage; omit for the full baseline")
    show = commands.add_parser("show", help="Print only the requested complete records")
    show.add_argument("identifiers", nargs="+")
    index = commands.add_parser("index", help="Print one compact index")
    index.add_argument("kind", choices=("antipattern", "technique"))
    commands.add_parser("build-index", help="Regenerate the two Markdown indexes")
    commands.add_parser("check", help="Validate records, references, indexes and core size")
    stats = commands.add_parser("stats", help="Measure text size and example context packets")
    stats.add_argument("--encoding", help="Optional tiktoken encoding, e.g. o200k_base")
    args = parser.parse_args()
    try:
        records = load_records()
        if args.command in ("start", "show"):
            lookup = {record.identifier: record for record in records}
            requested = (
                list(START_STAGES[args.stage] if args.stage else START_IDS) if args.command == "start"
                else list(dict.fromkeys(item.upper() for item in args.identifiers))
            )
            missing = [identifier for identifier in requested if identifier not in lookup]
            if missing:
                raise ValueError("Unknown identifiers: " + ", ".join(missing))
            for number, identifier in enumerate(requested):
                if number:
                    print()
                print(lookup[identifier].render(), end="")
        elif args.command == "index":
            print(render_index(records, args.kind), end="")
        elif args.command == "build-index":
            outputs = {
                "antipattern-index.md": render_index(records, "antipattern"),
                "technique-index.md": render_index(records, "technique"),
            }
            for filename, content in outputs.items():
                (REFERENCES / filename).write_text(content, encoding="utf-8")
            print("Updated both indexes.")
        elif args.command == "check":
            errors = validate(records)
            if errors:
                for error in errors:
                    print(f"ERROR: {error}", file=sys.stderr)
                return 1
            antipatterns = sum(r.kind == "antipattern" for r in records)
            techniques = sum(r.kind == "technique" for r in records)
            print(f"OK: {antipatterns} antipatterns, {techniques} techniques; references and indexes valid.")
        elif args.command == "stats":
            show_stats(records, args.encoding)
    except (OSError, UnicodeError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
