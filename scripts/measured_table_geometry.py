"""Bounded Stage42 bordered-table cell attribution; text never selects a cell."""

from pathlib import Path


def geometry(pdf: Path, columns: int, rows: int):
    import pdfplumber

    with pdfplumber.open(pdf) as document:
        page = document.pages[0]
        vertical = [o for o in page.lines if abs(o["x1"] - o["x0"]) < 0.01 and o["bottom"] - o["top"] > 40]
        x = sorted({round(o["x0"], 4) for o in vertical})
        if len(x) != columns + 1 or len(vertical) != columns + 1:
            raise ValueError("Ambiguous vertical table group")
        top, bottom = min(o["top"] for o in vertical), max(o["bottom"] for o in vertical)
        horizontal = [
            o
            for o in page.lines
            if top - 0.4 <= o["top"] <= bottom + 0.4 and abs(o["bottom"] - o["top"]) < 0.01 and o["x1"] - o["x0"] > 40
        ]
        y = sorted({round(o["top"], 4) for o in horizontal})
        if len(y) != rows + 1:
            raise ValueError("Ambiguous row rules")
        for line in horizontal:
            half = line["linewidth"] / 2
            if abs(line["x0"] - (x[0] - half)) > 0.05 or abs(line["x1"] - (x[-1] + half)) > 0.05:
                raise ValueError("Not a rectangular unmerged table")
        for line in vertical:
            half = line["linewidth"] / 2
            if abs(line["top"] - y[0]) > half + 0.05 or abs(line["bottom"] - y[-1]) > half + 0.05:
                raise ValueError("Segment ends do not corroborate rows")
        cells = [[] for _ in range(columns * rows)]
        for char in page.chars:
            cx, cy = (char["x0"] + char["x1"]) / 2, (char["top"] + char["bottom"]) / 2
            if not y[0] < cy < y[-1]:
                continue
            hits = [
                (r, c) for r in range(rows) for c in range(columns) if x[c] < cx < x[c + 1] and y[r] < cy < y[r + 1]
            ]
            if len(hits) != 1:
                raise ValueError("Ambiguous glyph polygon")
            r, c = hits[0]
            if char["x0"] <= x[c] or char["x1"] >= x[c + 1]:
                raise ValueError("Crossing glyph")
            cells[r * columns + c].append(char)
        result = []
        for index, chars in enumerate(cells):
            if not chars:
                raise ValueError("Empty origin")
            result.append(
                {
                    "row": index // columns,
                    "column": index % columns,
                    "text": "".join(c["text"] for c in chars if not c["text"].isspace()),
                    "baselines": sorted({round(page.height - c["matrix"][5], 4) for c in chars}),
                    "fonts": sorted({(c["fontname"].split("+")[-1], round(c["size"], 5)) for c in chars}),
                }
            )
        if any(len(c["baselines"]) != 1 for c in result):
            raise ValueError("Not single line")
        return {"x": x, "y": y, "cells": result, "pages": len(document.pages)}
