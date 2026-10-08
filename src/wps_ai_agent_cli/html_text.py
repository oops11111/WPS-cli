from __future__ import annotations

import codecs
import re


_META_CHARSET = re.compile(rb"""<meta[^>]+charset\s*=\s*["']?\s*([A-Za-z0-9_.:-]+)""", re.IGNORECASE)


def decode_html_bytes(raw: bytes) -> tuple[str, str, str | None]:
    """Decode HTML without silently corrupting non-UTF-8 text.

    Order: BOM, strict UTF-8, a charset declared in the first 2 KiB, then a lossy
    UTF-8 fallback that reports the replacement. Returns (text, encoding, warning).
    """
    if raw.startswith(codecs.BOM_UTF8):
        return raw[len(codecs.BOM_UTF8):].decode("utf-8", errors="replace"), "utf-8-sig", None
    if raw.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        try:
            return raw.decode("utf-16"), "utf-16", None
        except UnicodeDecodeError:
            pass
    try:
        return raw.decode("utf-8"), "utf-8", None
    except UnicodeDecodeError:
        pass
    match = _META_CHARSET.search(raw[:2048])
    if match:
        declared = match.group(1).decode("ascii", errors="ignore")
        try:
            return raw.decode(codecs.lookup(declared).name), declared.lower(), None
        except (LookupError, UnicodeDecodeError):
            pass
    return (
        raw.decode("utf-8", errors="replace"),
        "utf-8-replace",
        "Input is not valid UTF-8 and declares no usable charset; undecodable bytes were replaced and text may be corrupted.",
    )
