"""Markdown <-> HTML and DOCX (P13-012).

Markdown is read with markdown-it-py (the ``markdown`` extra: CommonMark plus GFM tables and strikethrough) when it
is installed, else with the built-in reader below, which covers headings, paragraphs, emphasis, code, links, images,
nested lists, block quotes, fenced code, rules and GFM tables. Writing Markdown walks the HTML tree, so DOCX goes
DOCX -> clean HTML -> Markdown; a DOCX is made from Markdown through html-editable.
"""

from __future__ import annotations

import base64
import html
import re
import tempfile
from pathlib import Path
from typing import Any

from .conversion_paths import check_paths

MARKDOWN = {".md", ".markdown"}

# ------------------------------------------------------------------------------------------- markdown -> html


def _inline(text: str) -> str:
    """Inline Markdown to HTML: code, images, links, bold, italic, strikethrough and hard breaks."""
    codes: list[str] = []

    def keep(match: re.Match) -> str:
        codes.append(f"<code>{html.escape(match.group(2), quote=False)}</code>")
        return f"\x00{len(codes) - 1}\x00"

    text = re.sub(r"(`+)(.+?)\1", keep, text)
    text = html.escape(text, quote=False)
    text = re.sub(
        r"!\[([^\]]*)\]\(([^)\s]+)(?:\s+&quot;[^&]*&quot;)?\)",
        lambda m: f'<img src="{html.escape(m.group(2))}" alt="{html.escape(m.group(1))}">',
        text,
    )
    text = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", lambda m: f'<a href="{html.escape(m.group(2))}">{m.group(1)}</a>', text)
    text = re.sub(r"(\*\*|__)(?=\S)(.+?)(?<=\S)\1", r"<strong>\2</strong>", text)
    text = re.sub(r"(?<![*\w])\*(?=\S)(.+?)(?<=\S)\*(?!\*)", r"<em>\1</em>", text)
    text = re.sub(r"(?<![_\w])_(?=\S)(.+?)(?<=\S)_(?![_\w])", r"<em>\1</em>", text)
    text = re.sub(r"~~(?=\S)(.+?)(?<=\S)~~", r"<s>\1</s>", text)
    text = re.sub(r"(?: {2,}|\\)\n", "<br>\n", text)
    return re.sub(r"\x00(\d+)\x00", lambda m: codes[int(m.group(1))], text)


_LIST = re.compile(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$")
_TABLE_RULE = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")


def _cells(line: str) -> list[str]:
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|") and not line.endswith("\\|"):
        line = line[:-1]
    return [cell.strip().replace("\\|", "|") for cell in re.split(r"(?<!\\)\|", line)]


def _list_html(items: list[tuple[int, str, str]]) -> str:
    """Nested lists from (indent, marker, text) items."""
    out: list[str] = []
    stack: list[tuple[int, str]] = []
    for indent, marker, text in items:
        kind = "ol" if marker[0].isdigit() else "ul"
        while stack and indent < stack[-1][0]:
            out.append(f"</li></{stack.pop()[1]}>")
        if stack and indent == stack[-1][0]:
            if stack[-1][1] != kind:
                out.append(f"</li></{stack.pop()[1]}>")
            else:
                out.append("</li>")
        if not stack or indent > stack[-1][0]:
            start = int(marker[:-1]) if kind == "ol" and marker[:-1].isdigit() and int(marker[:-1]) != 1 else None
            out.append(f"<{kind}" + (f' start="{start}"' if start else "") + ">")
            stack.append((indent, kind))
        out.append(f"<li>{_inline(text)}")
    while stack:
        out.append(f"</li></{stack.pop()[1]}>")
    return "".join(out)


def _blocks(lines: list[str]) -> list[str]:
    out: list[str] = []
    paragraph: list[str] = []
    i = 0

    def flush() -> None:
        if paragraph:
            out.append(f"<p>{_inline(chr(10).join(paragraph))}</p>")
            paragraph.clear()

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        fence = re.match(r"^\s*(```|~~~)\s*([\w+-]*)", line)
        if fence:
            flush()
            marker, language = fence.group(1), fence.group(2)
            body = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith(marker):
                body.append(lines[i])
                i += 1
            css = f' class="language-{language}"' if language else ""
            out.append(f"<pre><code{css}>{html.escape(chr(10).join(body), quote=False)}</code></pre>")
            i += 1
            continue
        if not stripped:
            flush()
            i += 1
            continue
        heading = re.match(r"^(#{1,6})\s+(.*?)\s*#*\s*$", stripped)
        if heading:
            flush()
            level = len(heading.group(1))
            out.append(f"<h{level}>{_inline(heading.group(2))}</h{level}>")
            i += 1
            continue
        if re.fullmatch(r"(\*\s*){3,}|(-\s*){3,}|(_\s*){3,}", stripped) and not paragraph:
            out.append("<hr>")
            i += 1
            continue
        if paragraph and re.fullmatch(r"=+|-+", stripped):
            level = 1 if stripped[0] == "=" else 2
            out.append(f"<h{level}>{_inline(' '.join(paragraph))}</h{level}>")
            paragraph.clear()
            i += 1
            continue
        if stripped.startswith(">"):
            flush()
            quoted = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quoted.append(re.sub(r"^\s*>\s?", "", lines[i]))
                i += 1
            out.append("<blockquote>" + "".join(_blocks(quoted)) + "</blockquote>")
            continue
        if "|" in stripped and i + 1 < len(lines) and _TABLE_RULE.match(lines[i + 1]) and "-" in lines[i + 1]:
            flush()
            header = _cells(line)
            aligns = []
            for rule in _cells(lines[i + 1]):
                aligns.append(
                    "center"
                    if rule.startswith(":") and rule.endswith(":")
                    else "right"
                    if rule.endswith(":")
                    else "left"
                    if rule.startswith(":")
                    else ""
                )
            i += 2
            rows = []
            while i < len(lines) and "|" in lines[i] and lines[i].strip():
                rows.append(_cells(lines[i]))
                i += 1

            def cell(tag: str, text: str, index: int, aligns: list[str] = aligns) -> str:
                align = aligns[index] if index < len(aligns) and aligns[index] else ""
                style = f' style="text-align:{align}"' if align else ""
                return f"<{tag}{style}>{_inline(text)}</{tag}>"

            head = "".join(cell("th", text, n) for n, text in enumerate(header))
            body = "".join(
                "<tr>" + "".join(cell("td", row[n] if n < len(row) else "", n) for n in range(len(header))) + "</tr>"
                for row in rows
            )
            out.append(f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>")
            continue
        item = _LIST.match(line)
        if item and (not paragraph or not item.group(1)):
            flush()
            items: list[tuple[int, str, str]] = []
            while i < len(lines):
                match = _LIST.match(lines[i])
                if match:
                    items.append((len(match.group(1).expandtabs(4)), match.group(2), match.group(3)))
                elif lines[i].strip() and items and lines[i].startswith((" ", "\t")):
                    indent, marker, text = items[-1]
                    items[-1] = (indent, marker, text + " " + lines[i].strip())
                else:
                    break
                i += 1
            out.append(_list_html(items))
            continue
        paragraph.append(line.rstrip("\n") if line.endswith("  ") else stripped)
        i += 1
    flush()
    return out


def _builtin(text: str) -> str:
    return "\n".join(_blocks(text.replace("\r\n", "\n").replace("\r", "\n").split("\n")))


def markdown_engine() -> str:
    try:
        import markdown_it  # noqa: F401
    except ImportError:
        return "builtin"
    return "markdown-it-py"


def markdown_to_html_body(text: str) -> tuple[str, str]:
    """The HTML for a Markdown text, and which reader made it."""
    try:
        from markdown_it import MarkdownIt
    except ImportError:
        return _builtin(text), "builtin"
    parser = MarkdownIt("commonmark", {"html": False}).enable(["table", "strikethrough"])
    return parser.render(text), "markdown-it-py"


def markdown_to_html_text(text: str, title: str = "") -> str:
    body, _engine = markdown_to_html_body(text)
    if not title:
        heading = re.search(r"<h1>(.*?)</h1>", body)
        title = re.sub(r"<[^>]+>", "", heading.group(1)) if heading else "Document"
    return (
        '<!doctype html>\n<html lang="zh-CN">\n<head>\n<meta charset="utf-8">\n'
        f"<title>{html.escape(title, quote=False)}</title>\n<style>\n"
        "body{font-family:'Microsoft YaHei','Noto Sans CJK SC',sans-serif;line-height:1.6;margin:24px}\n"
        "table{border-collapse:collapse}th,td{border:1px solid #999;padding:4px 8px}\n"
        "pre{background:#f5f5f5;padding:8px}code{font-family:Consolas,monospace}\n"
        "blockquote{border-left:4px solid #ccc;margin-left:0;padding-left:12px;color:#555}\n"
        "</style>\n</head>\n<body>\n" + body + "\n</body>\n</html>\n"
    )


def _read_markdown(source: Path) -> str:
    from .tabular import decode_text

    text, _encoding = decode_text(source.read_bytes())
    return text


def md_to_html(input_path: str | Path, output_path: str | Path) -> tuple[bool, dict[str, Any], list[dict[str, str]]]:
    source, destination, errors = check_paths(input_path, output_path, MARKDOWN, {".html", ".htm"})
    if errors:
        return False, {}, errors
    text = _read_markdown(source)
    body, engine = markdown_to_html_body(text)
    destination.write_text(markdown_to_html_text(text), encoding="utf-8")
    return (
        True,
        {
            "input_path": str(source),
            "output_path": str(destination),
            "format": "html",
            "markdown_reader": engine,
            "warnings": [] if engine != "builtin" else [],
        },
        [],
    )


def md_to_office(
    input_path: str | Path, output_path: str | Path, use_browser: bool = True
) -> tuple[bool, dict[str, Any], list[dict[str, str]]]:
    """Markdown to DOCX (or PPTX, XLSX) through a temporary HTML file next to the source, so images resolve."""
    source, destination, errors = check_paths(input_path, output_path, MARKDOWN, {".docx", ".pptx", ".xlsx"})
    if errors:
        return False, {}, errors
    from .html_office import convert_html_to_office

    text = _read_markdown(source)
    _body, engine = markdown_to_html_body(text)
    handle = tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=source.parent, prefix=".wps-md-", suffix=".html", delete=False
    )
    try:
        with handle:
            handle.write(markdown_to_html_text(text, source.stem))
        ok, data, errors = convert_html_to_office(
            handle.name, destination, destination.suffix.casefold().lstrip("."), use_browser=use_browser
        )
    finally:
        Path(handle.name).unlink(missing_ok=True)
    if ok:
        data["input_path"] = str(source)
        data["markdown_reader"] = engine
    return ok, data, errors


# ------------------------------------------------------------------------------------------- html -> markdown


def _escape_md(text: str) -> str:
    return re.sub(r"([\\`*_\[\]#|~])", r"\\\1", text)


class _Writer:
    def __init__(self, source: Path, destination: Path) -> None:
        self.source = source
        self.folder = destination.with_name(destination.stem + "_files")
        self.images = 0
        self.warnings: set[str] = set()

    def image(self, node) -> str:
        src = node.attrs.get("src", "")
        alt = node.attrs.get("alt", "")
        if src.startswith("data:"):
            header, _, encoded = src.partition(",")
            extension = {"image/png": ".png", "image/jpeg": ".jpg", "image/gif": ".gif"}.get(
                header[5:].split(";", 1)[0].casefold(), ".png"
            )
            try:
                data = base64.b64decode(encoded)
            except ValueError:
                return ""
            self.folder.mkdir(exist_ok=True)
            self.images += 1
            path = self.folder / f"image{self.images:03d}{extension}"
            path.write_bytes(data)
            src = f"{self.folder.name}/{path.name}"
        else:
            self.images += 1
        return f"![{_escape_md(alt)}]({src.replace(' ', '%20')})"

    def inline(self, node, in_table: bool = False) -> str:
        from .html_editable import _Node, style_formats

        parts: list[str] = []
        for child in node.children:
            if isinstance(child, str):
                parts.append(_escape_md(re.sub(r"\s+", " ", child)))
                continue
            if not isinstance(child, _Node) or child.tag in {"script", "style", "ul", "ol", "table"}:
                continue
            tag = child.tag
            if tag == "br":
                parts.append("<br>" if in_table else "  \n")
                continue
            if tag == "img":
                parts.append(self.image(child))
                continue
            inner = self.inline(child, in_table)
            if not inner.strip():
                parts.append(inner)
                continue
            formats = style_formats(child.attrs.get("style", ""))
            lead = inner[: len(inner) - len(inner.lstrip())]
            trail = inner[len(inner.rstrip()) :]
            core = inner.strip()
            if tag == "code":
                core = f"`{_text_of(child)}`"
            if tag in {"s", "del", "strike"} or formats.get("strike"):
                core = f"~~{core}~~"
            if tag in {"em", "i"} or formats.get("italic"):
                core = f"*{core}*"
            if tag in {"strong", "b"} or formats.get("bold"):
                core = f"**{core}**"
            if tag == "sub":
                core = f"<sub>{core}</sub>"
            if tag == "sup":
                core = f"<sup>{core}</sup>"
            if tag == "a" and child.attrs.get("href"):
                core = f"[{core}]({child.attrs['href']})"
            parts.append(lead + core + trail)
        return "".join(parts)

    def table(self, node) -> str:
        from .html_editable import table_grid

        grid, merges = table_grid(node)
        if not grid:
            return ""
        if merges:
            self.warnings.add("Markdown tables have no merged cells: a merged cell's text is in its first cell.")
        seen: set[int] = set()
        rows = []
        for row in grid:
            cells = []
            for cell in row:
                if cell is None or id(cell) in seen:
                    cells.append("")
                    continue
                seen.add(id(cell))
                text = self.inline(cell, in_table=True).strip().replace("|", "\\|").replace("\n", "<br>")
                if cell.tag == "th" and re.fullmatch(r"\*\*[^*]+\*\*", text):
                    text = text[2:-2]  # a header cell is bold already
                cells.append(text)
            rows.append(cells)
        width = max(len(r) for r in rows)
        rows = [r + [""] * (width - len(r)) for r in rows]
        lines = ["| " + " | ".join(rows[0]) + " |", "|" + "|".join(["---"] * width) + "|"]
        lines += ["| " + " | ".join(r) + " |" for r in rows[1:]]
        return "\n".join(lines)

    def blocks(self, node, depth: int = 0) -> list[str]:
        from .html_editable import _HEADINGS, _Node

        out: list[str] = []
        pending: list[str] = []

        def flush() -> None:
            text = "".join(pending).strip()
            if text:
                out.append(text)
            pending.clear()

        for child in node.children:
            if isinstance(child, str):
                if child.strip():
                    pending.append(_escape_md(re.sub(r"\s+", " ", child)))
                continue
            if not isinstance(child, _Node):
                continue
            tag = child.tag
            classes = child.attrs.get("class", "").split()
            if tag in {"script", "style", "head", "title", "template"} or "notes" in classes:
                continue
            if tag in _HEADINGS:
                flush()
                out.append("#" * _HEADINGS[tag] + " " + self.inline(child).strip())
            elif tag == "p" or tag in {"figcaption", "caption", "dt", "dd", "summary", "address"}:
                flush()
                text = self.inline(child).strip()
                if text:
                    out.append(text)
            elif tag in {"ul", "ol"}:
                flush()
                out.append(self.list(child, 0))
            elif tag == "table":
                flush()
                caption = next((c for c in child.children if isinstance(c, _Node) and c.tag == "caption"), None)
                if caption is not None:
                    out.append(self.inline(caption).strip())
                out.append(self.table(child))
            elif tag == "pre":
                flush()
                language = ""
                code = next((c for c in child.children if isinstance(c, _Node) and c.tag == "code"), None)
                if code is not None:
                    match = re.search(r"language-([\w+-]+)", code.attrs.get("class", ""))
                    language = match.group(1) if match else ""
                out.append(f"```{language}\n{_text_of(child).rstrip(chr(10))}\n```")
            elif tag == "blockquote":
                flush()
                inner = self.blocks(child, depth)
                out.append("\n>\n".join("\n".join("> " + line for line in b.split("\n")) for b in inner))
            elif tag == "hr":
                flush()
                out.append("---")
            elif tag == "img":
                flush()
                out.append(self.image(child))
            elif tag in {"div", "section", "article", "main", "header", "footer", "aside", "figure", "body", "html"}:
                flush()
                out += self.blocks(child, depth)
            else:
                pending.append(self.inline(_wrap(child)))
        flush()
        return out

    def list(self, node, depth: int) -> str:
        from .html_editable import _Node

        lines: list[str] = []
        number = int(node.attrs.get("start", "1") or 1) if node.attrs.get("start", "1").isdigit() else 1
        for item in node.children:
            if not isinstance(item, _Node) or item.tag != "li":
                continue
            marker = f"{number}." if node.tag == "ol" else "-"
            number += 1
            text = self.inline(item).strip()
            if text or item.attrs.get("style", "").replace(" ", "") != "list-style:none":
                lines.append("  " * depth * (2 if node.tag == "ol" else 1) + f"{marker} {text}")
            for nested in item.children:
                if isinstance(nested, _Node) and nested.tag in {"ul", "ol"}:
                    lines.append(self.list(nested, depth + 1 if text else depth))
        return "\n".join(lines)


def _wrap(node):
    from .html_editable import _Node

    return _Node("span", {}, [node])


def _text_of(node) -> str:
    from .html_editable import _Node

    parts: list[str] = []
    for child in node.children:
        if isinstance(child, str):
            parts.append(child)
        elif isinstance(child, _Node):
            parts.append("\n" if child.tag == "br" else _text_of(child))
    return "".join(parts)


def html_to_markdown(source: Path, destination: Path) -> tuple[str, _Writer]:
    from .html_editable import _TreeParser
    from .html_text import decode_html_bytes

    text, _encoding, _warning = decode_html_bytes(source.read_bytes())
    parser = _TreeParser()
    parser.feed(text)
    parser.close()
    writer = _Writer(source, destination)
    blocks = writer.blocks(parser.root)
    return "\n\n".join(b for b in blocks if b.strip()) + "\n", writer


def to_markdown(input_path: str | Path, output_path: str | Path) -> tuple[bool, dict[str, Any], list[dict[str, str]]]:
    """HTML, DOCX, PPTX or XLSX to Markdown; images go to ``<name>_files/``."""
    source, destination, errors = check_paths(
        input_path, output_path, {".html", ".htm", ".docx", ".pptx", ".xlsx"}, MARKDOWN
    )
    if errors:
        return False, {}, errors
    warnings: list[str] = []
    if source.suffix.casefold() in {".html", ".htm"}:
        markdown, writer = html_to_markdown(source, destination)
    else:
        from .office_html import office_to_html

        with tempfile.TemporaryDirectory() as tmp:
            page = Path(tmp) / f"{source.stem}.html"
            ok, data, errors = office_to_html(source, page)
            if not ok:
                return False, {}, errors
            warnings += data.get("warnings", [])
            markdown, writer = html_to_markdown(page, destination)
        if source.suffix.casefold() == ".pptx":
            warnings.append("Slide positions, animations and transitions have no Markdown form and were omitted.")
    destination.write_text(markdown, encoding="utf-8")
    return (
        True,
        {
            "input_path": str(source),
            "output_path": str(destination),
            "format": "md",
            "images": writer.images,
            "image_folder": str(writer.folder) if writer.folder.exists() else None,
            "warnings": warnings + sorted(writer.warnings),
        },
        [],
    )
