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
PAGE_CHAR_LIMIT = 6_000
MAX_PAGE_CHAR_LIMIT = 8_000
START_IDS = (
    "TXT-01", "TXT-03", "TXT-04", "TXT-08", "TXT-11", "TXT-37",
    "TXT-35", "TXT-36", "TXT-41", "TXT-42",
    "LAY-11", "LAY-17", "LAY-18", "LAY-19", "TYP-02", "TYP-09", "TYP-14",
    "CTL-13", "CTL-14", "CTL-15", "CTL-16", "CTL-17", "CTL-18", "CTL-19", "CTL-20", "PAG-13", "COL-05",
    "IMG-09", "MOT-08", "MOT-13", "MOT-14", "MOT-15", "PRC-10", "PRC-11", "PRC-12", "PRC-15", "PRC-16",
)
START_STAGES = {
    "content": (
        "TXT-01", "TXT-03", "TXT-04", "TXT-08", "TXT-11", "TXT-37",
        "TXT-35", "TXT-36", "TXT-41", "TXT-42",
        "LAY-18", "PRC-12", "PRC-16",
    ),
    "composition": (
        "LAY-11", "LAY-17", "LAY-19", "TYP-02", "TYP-09", "TYP-14",
        "IMG-09", "PRC-10", "PRC-15", "TXT-41",
    ),
    "detail": ("CTL-13", "CTL-14", "CTL-15", "CTL-16", "CTL-17", "CTL-18", "CTL-19", "CTL-20", "PAG-13", "TYP-14", "COL-05", "MOT-08", "MOT-13", "MOT-14", "MOT-15", "PRC-11"),
}
START_RESOURCES = {
    "content": ("content-workflow.md", "brief-and-decisions.md"),
    "composition": ("ready-solutions.md", "resource-selection.md", "art-direction.md", "resource-pipeline.md"),
    "detail": ("review.md", "regression-workflow.md"),
}
START_RESULTS = {
    "content": "Результат: точные тексты, материал и действия в content.md; существенные ответы/делегирование/неизвестное в design-state.md. Прочитай тексты без оформления до разметки.",
    "composition": "Результат: профиль тегов проекта, реальные тематические запросы и изученные альтернативы с обоснованным отбором; три схемы с рекомендацией; один черновик с настоящим содержанием и выводами широкого/узкого просмотра. Порученный выбор сделай сам.",
    "detail": "Результат: проработанные участки и полный нужный цикл управления; фактический текст сопоставлен с содержанием; функция, визуальный вид и свойства источников проверены отдельно на текущей версии. Непроверенное обозначено.",
}
START_TRANSITIONS = {
    "content": "До разметки: выясни или получи явное делегирование неизвестных решений дизайн-кода, предложи проектные варианты с рекомендацией и отдельно подготовь содержание. Вопросы выбирай по references/design-interview.md: перечень запрошенных фич не закрывает их существенный сценарий, контакт не заменяет дизайн-бриф. Scroll/parallax без основания в запросе, пользовательском референсе или принятом решении не добавляй в опрос; заданное и делегированное учитывай. Ресерч можно вести параллельно; молчание не закрывает бриф. Сохраняй основание ответа/делегирования; proposed не равно approved. Продолжай короткие обсуждения оставшихся значимых развилок, не завершая бриф контактным вопросом. Факты спрашивай прямо, варианты придумывай для решений.",
    "composition": "До макета: выполни глубокий подбор по references/resource-selection.md. Выведи недостающие теги из общего направления, композиции, материала и UX, преобразуй их в реальные запросы внутри тематических каталогов/API/MCP либо целевой программный поиск. Главная, popular/featured и первые знакомые элементы не завершают подбор. Изучи детали и содержательно разные альтернативы для одной задачи; сопоставь стиль, компоновку, UX, материал и выполнимость до принятия, даже если первый кандидат работает. Ранее использованный компонент заново проходит этот отбор. Сохрани фактические запросы, наблюдения и основание остановки; план и receipt не заменяют выбор. Для существенных участков повторяй ресурсную контрольную точку: подбор → адаптация → проверка свойства. Пригодную основу можно использовать повторно; искусственной квоты загрузок нет. Покажи три схемы с рекомендацией; для средств используй references/style-directions.md и references/technique-selection.md. Делегирование не отменяет ресерч, локальная правка не требует нового направления.",
    "detail": "До детализации: проверь бриф, фактические источники и решения по коду, предложенные схемы и выбранный просмотренный макет в design-state.md. Если подготовка лишь запланирована, вернись к незавершённому шагу. Прочитай references/review.md: проверь настоящий масштаб, цветовые роли, обещанный результат и полный цикл нужных взаимодействий. Функция, рисунок и устойчивость проверяются отдельно. Нужные проверки известных ошибок: library.py checks ID... . Для рабочего web/desktop/mobile выбери относящиеся ветки references/platform-workflows.md; стандартная семантика управления сохраняется. Локальную правку не расширяй до нового цикла.",
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


def render_start_guidance(stage: str | None) -> str:
    current = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    revision = re.search(r"Редакция процесса: (\d+)\.", current)
    stamp = "Редакция процесса: " + (revision.group(1) if revision else "не указана") + ". Источник: " + str(ROOT / "SKILL.md") + "\n\n"
    if stage is None:
        return stamp + ("## Начало работы\n\nНовый интерфейс: start --stage content, затем composition и detail. Локальная правка: только затронутые записи через show/checks. Полный маршрут: references/staged-workflow.md. Справочник: read <файл.md>, раздел: --section <заголовок>, структура: --list-sections. Обязательные страницы дочитывай; сохранение файла не означает чтение.\n")
    parts = ["## Переход этапа: " + stage, "", START_TRANSITIONS[stage], "", START_RESULTS[stage], "", "Прочитай относящиеся к задаче инструкции (полный текст доступен через read; длинные ответы разбиты на страницы):"]
    for filename in START_RESOURCES[stage]:
        parts.append("- references/" + filename + " — library.py read " + filename)
    if stage == "composition":
        parts.append("- При новой текстовой системе и проблемах чтения/интервалов: references/font-research.md → nomoreslop-typography по фактическому каталогу навыков. Передай строки, locale/script, роль и контекст. Прими шкалу/ритм/адаптацию и проверки; новому шрифту — сравнение, лицензию, файлы и cmap/shaping/render. Design проверяет целую композицию. Локальная правка не требует смены семьи и второго брифа.")
    if stage == "composition":
        parts.append("- Для нового цветового направления и проблем палитры: references/color-research.md → nomoreslop-color по доступному каталогу. Прими исследованные источники, роли и пару light/dark каждого предложения; design проверяет интенсивность, площади и целую композицию. Не повторяй общий бриф и не меняй принятую систему ради ресерча.")
    parts.extend(("", "Ни отметка этапа, ни автоматическая проверка не подтверждают качество. Сохраняй конкретные результаты, версию и ограничения в актуальном состоянии.", ""))
    return stamp + "\n".join(parts)


def paginate(text: str, limit: int = PAGE_CHAR_LIMIT) -> list[str]:
    """Lossless chunks; reserve space for explicit page/continuation metadata."""
    if not 1_600 <= limit <= MAX_PAGE_CHAR_LIMIT:
        raise ValueError(f"Page limit must be between 1600 and {MAX_PAGE_CHAR_LIMIT}")
    payload_limit = limit - 600
    pages = []
    rest = text
    while len(rest) > payload_limit:
        boundary = rest.rfind("\n\n", 0, payload_limit)
        if boundary < payload_limit // 2:
            boundary = rest.rfind("\n", 0, payload_limit)
        if boundary < payload_limit // 2:
            boundary = payload_limit
        elif rest[boundary:boundary + 2] == "\n\n":
            boundary += 2
        else:
            boundary += 1
        pages.append(rest[:boundary])
        rest = rest[boundary:]
    pages.append(rest)
    return pages


def render_page(text: str, page: int, limit: int, command: str) -> str:
    pages = paginate(text, limit)
    if not 1 <= page <= len(pages):
        raise ValueError(f"Page must be between 1 and {len(pages)}")
    header = f"[Страница {page}/{len(pages)}; предел ответа {limit} символов]\n\n"
    if page < len(pages) and len(command) > 330:
        footer = f"\n[Есть продолжение. Повтори исходный вызов с тем же выбором, заменив/добавив --page {page + 1} --limit {limit}; длинный выбор здесь не повторяется.]\n"
    elif page < len(pages):
        footer = f"\n[Есть продолжение. Дочитай: python <путь-к-скиллу>/scripts/library.py {command} --page {page + 1} --limit {limit}]\n"
    else:
        footer = "\n[Конец выбранного материала; это не отметка о выполнении этапа.]\n"
    result = header + pages[page - 1] + footer
    if len(result) > limit:
        raise ValueError("Page metadata exceeded reserved space; use a shorter selector")
    return result


def read_reference(filename: str, section: str | None = None, list_sections: bool = False) -> str:
    source = (REFERENCES / filename).resolve()
    if not source.is_relative_to(REFERENCES.resolve()) or source.suffix != ".md" or not source.is_file():
        raise ValueError("Read expects an existing .md file inside references/")
    content = source.read_text(encoding="utf-8")
    headings = list(re.finditer(r"^(#{1,6}) (.+)$", content, re.M))
    if list_sections:
        return "\n".join("  " * (len(h.group(1)) - 1) + h.group(2) for h in headings) + "\n"
    if section is None:
        return content
    exact = [h for h in headings if h.group(2).casefold() == section.casefold()]
    matches = exact or [h for h in headings if section.casefold() in h.group(2).casefold()]
    if len(matches) != 1:
        raise ValueError("Section must select one heading; use --list-sections")
    heading = matches[0]
    following = [h for h in headings if h.start() > heading.start() and len(h.group(1)) <= len(heading.group(1))]
    end = following[0].start() if following else len(content)
    return content[heading.start():end]


def validate_pattern_checks(data, records: list[Record]) -> list[str]:
    errors = []
    if not isinstance(data, dict) or data.get("schema_version") != 1 or not isinstance(data.get("patterns"), list):
        return ["pattern-checks.json needs schema_version:1 and patterns array"]
    expected = {record.identifier for record in records if record.kind == "antipattern"}
    seen = set()
    for item in data["patterns"]:
        if not isinstance(item, dict):
            errors.append("Pattern check must be an object"); continue
        identity = item.get("id")
        if not isinstance(identity, str) or identity not in expected or identity in seen:
            errors.append(f"Unknown or duplicate pattern check: {identity}"); continue
        seen.add(identity)
        canonical = item.get("canonical", {})
        if not isinstance(canonical, dict) or not isinstance(canonical.get("path"), str):
            errors.append(f"Missing canonical path: {identity}")
        else:
            target = (REFERENCES / canonical["path"]).resolve()
            record = next(record for record in records if record.identifier == identity)
            if not target.is_relative_to(REFERENCES.resolve()) or target != record.source.resolve():
                errors.append(f"Canonical path mismatch: {identity}")
        check = item.get("check", {})
        if not isinstance(check, dict) or any(not isinstance(check.get(key), str) or not check[key].strip() for key in ("action", "expected", "counterexample")):
            errors.append(f"Incomplete action/expected/counterexample: {identity}")
        grounds = item.get("grounding", [])
        if not isinstance(grounds, list) or not grounds:
            errors.append(f"Missing grounding: {identity}"); continue
        for ground in grounds:
            if not isinstance(ground, dict) or ground.get("type") not in {"user_policy", "professional", "criterion", "evidence"}:
                errors.append(f"Unknown grounding type: {identity}"); continue
            if any(not isinstance(ground.get(key), str) or not ground[key].strip() for key in ("context", "limits")):
                errors.append(f"Grounding needs scope and limits: {identity}")
            if ground["type"] != "user_policy" and not str(ground.get("url", "")).startswith("https://"):
                errors.append(f"Grounding needs primary URL: {identity}")
    for identity in sorted(expected - seen):
        errors.append(f"Missing pattern check: {identity}")
    return errors


def read_pattern_checks(records: list[Record]):
    data = json.loads((REFERENCES / "pattern-checks.json").read_text(encoding="utf-8"))
    errors = validate_pattern_checks(data, records)
    if errors:
        raise ValueError("; ".join(errors))
    return {item["id"]: item for item in data["patterns"]}


def render_pattern_checks(identifiers, recipes) -> str:
    parts = ["# Проверки выбранных признаков", "", "Проверь текущий артефакт и границу; это задания для проверки, не выполненные тесты и не детектор авторства.", ""]
    for identity in identifiers:
        if identity not in recipes:
            raise ValueError(f"No antipattern check for {identity}")
        recipe = recipes[identity]
        parts.extend((f"## {identity}", "Каноническое правило: references/" + recipe["canonical"]["path"],
                      "Действие проверки: " + recipe["check"]["action"],
                      "Ожидаемое: " + recipe["check"]["expected"],
                      "Контрольное исключение: " + recipe["check"]["counterexample"]))
        for ground in recipe["grounding"]:
            parts.append("Основание (" + ground["type"] + "): " + ground["context"] + " " + ground.get("url", "") + " Граница: " + ground["limits"])
        parts.append("")
    return "\n".join(parts)


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
    lookup = {record.identifier: record for record in records}
    for stage, stage_ids in START_STAGES.items():
        payload = render_start_guidance(stage) + "\n" + "\n".join(lookup[key].render() for key in stage_ids)
        pages = paginate(payload)
        if "".join(pages) != payload:
            errors.append(f"Lossy stage pagination: {stage}")
        for page_number in range(1, len(pages) + 1):
            if len(render_page(payload, page_number, PAGE_CHAR_LIMIT, f"start --stage {stage}")) > PAGE_CHAR_LIMIT:
                errors.append(f"Stage page exceeds limit: {stage}/{page_number}")
    try:
        data = json.loads((REFERENCES / "pattern-checks.json").read_text(encoding="utf-8"))
        errors.extend(validate_pattern_checks(data, records))
    except (OSError, ValueError) as error:
        errors.append("Pattern checks: " + str(error))
    try:
        adapters = json.loads((REFERENCES / "source-adapters.json").read_text(encoding="utf-8"))
        sources = adapters.get("sources", [])
        identities = [row.get("id") for row in sources]
        urls = [row.get("saved_url") for row in sources]
        if adapters.get("schema_version") != 1 or len(sources) != 37 or len(set(identities)) != 37 or not all(isinstance(url, str) and url.startswith("https://") for url in urls):
            errors.append("Source adapter map must retain 35 bookmark entries + Awwwards + Colorsinspo with unique IDs")
    except (OSError, ValueError, TypeError, AttributeError) as error:
        errors.append("Source adapters: " + str(error))
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
        "all_baseline_records_example": core + render_start_guidance(None) + selected(*START_IDS),
        "all_baseline_with_brief_example": core + selected(*START_IDS)
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
    packets["start_route"] = render_page(render_start_guidance(None) + "\n", 1, PAGE_CHAR_LIMIT, "start")
    for stage, identifiers in START_STAGES.items():
        full_packet = render_start_guidance(stage) + "\n" + selected(*identifiers)
        packets[f"{stage}_start_full"] = full_packet
        packets[f"{stage}_start_page1"] = render_page(full_packet, 1, PAGE_CHAR_LIMIT, f"start --stage {stage}")
    all_markdown = "\n".join(
        source.read_text(encoding="utf-8") for source in sorted(ROOT.rglob("*.md"))
    )
    print(json.dumps({
        "antipatterns": sum(r.kind == "antipattern" for r in records),
        "techniques": sum(r.kind == "technique" for r in records),
        "encoding": encoding_name,
        "note": tokenizer_note,
        "packet_note": "*_start_full is the exact selected start payload before pagination; *_start_page1 and start_route are emitted CLI pages. Other *_example packets are constructed context examples, not mandatory output.",
        "core_character_budget": CORE_CHAR_BUDGET,
        "packets": {name: measure(text, encoding) for name, text in packets.items()},
        "all_markdown": measure(all_markdown, encoding),
        "per_file": per_file,
    }, ensure_ascii=False, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    start = commands.add_parser("start", help="Print baseline records, optionally limited to the current stage")
    start.add_argument("--stage", choices=tuple(START_STAGES), help="Load the current stage; omit to show the route")
    start.add_argument("--platform", choices=("web", "web-app", "desktop", "mobile"), help="Add a conditional platform route, not the whole platform guide")
    show = commands.add_parser("show", help="Print only the requested complete records")
    show.add_argument("identifiers", nargs="+")
    checks = commands.add_parser("checks", help="Print specific checks, positive counterexamples and grounding for selected antipattern IDs")
    checks.add_argument("identifiers", nargs="+")
    read = commands.add_parser("read", help="Read a reference file or one heading, with explicit continuation")
    read.add_argument("filename")
    read.add_argument("--section")
    read.add_argument("--list-sections", action="store_true")
    for paged_parser in (start, show, read, checks):
        paged_parser.add_argument("--page", type=int, default=1)
        paged_parser.add_argument("--limit", type=int, default=PAGE_CHAR_LIMIT, help="Maximum output characters, including page metadata (1600–8000)")
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
                list(START_STAGES[args.stage]) if args.command == "start" and args.stage else
                [] if args.command == "start" else
                list(dict.fromkeys(item.upper() for item in args.identifiers))
            )
            missing = [identifier for identifier in requested if identifier not in lookup]
            if missing:
                raise ValueError("Unknown identifiers: " + ", ".join(missing))
            payload = "\n".join(lookup[key].render() for key in requested)
            if args.command == "start":
                payload = render_start_guidance(args.stage) + "\n" + payload
                command = "start" + (f" --stage {args.stage}" if args.stage else "")
                if args.platform:
                    payload += "\nПлатформа: " + args.platform + ". Прочитай относящиеся сценарии references/platform-workflows.md; не загружай все ветки, не переписывай знакомое управление ради необычности.\n"
                    command += " --platform " + args.platform
            else:
                command = "show " + " ".join(requested)
            print(render_page(payload, args.page, args.limit, command), end="")
        elif args.command == "checks":
            requested = list(dict.fromkeys(item.upper() for item in args.identifiers))
            payload = render_pattern_checks(requested, read_pattern_checks(records))
            print(render_page(payload, args.page, args.limit, "checks " + " ".join(requested)), end="")
        elif args.command == "read":
            payload = read_reference(args.filename, args.section, args.list_sections)
            command = 'read "' + args.filename + '"'
            if args.section:
                command += ' --section "' + args.section + '"'
            if args.list_sections:
                command += " --list-sections"
            print(render_page(payload, args.page, args.limit, command), end="")
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
