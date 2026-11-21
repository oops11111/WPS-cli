"""Current browser qualification and exact original-five package gate; no WPS."""

import copy
import hashlib
import json
import sys
import zipfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from wps_ai_agent_cli import html_styles  # noqa:E402
from wps_ai_agent_cli.html_editable import _walk, convert_html_editable  # noqa:E402

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "artifacts/figure-image-indent-20261121"
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def verify_document_xml(before, after, case):
    from lxml import etree as XML

    if case == "A-report-docx":
        if before != after:
            raise ValueError("Fail-closed report changed")
        return []
    if case not in {"A-contract-docx", "A-manual-docx", "A-newsletter-docx", "A-pdfsource-docx"}:
        raise ValueError(case)
    a, b = XML.fromstring(before), XML.fromstring(after)
    oldmargin = a.find(".//" + W + "sectPr/" + W + "pgMar")
    newmargin = b.find(".//" + W + "sectPr/" + W + "pgMar")
    changes = []
    for side in ("left", "right"):
        if oldmargin.get(W + side) != "687" or newmargin.get(W + side) != "675":
            raise ValueError("Unexpected margins")
        newmargin.set(W + side, "687")
        changes.append({"attribute": "pgMar/" + side, "old": 687, "new": 675})
    if case == "A-contract-docx":
        oldtable = a.find(W + "body").findall(W + "tbl")[1]
        newtable = b.find(W + "body").findall(W + "tbl")[1]
        for table in (oldtable, newtable):
            if [int(c.get(W + "w")) for c in table.find(W + "tblGrid")] != [710, 724, 1370, 2729]:
                raise ValueError("Unexpected grid")
        width = int(a.find(".//" + W + "pgSz").get(W + "w"))
        if width != 11906 or (width - 2 * 687) / 4 != 2633 or (width - 2 * 675) / 4 != 2639:
            raise ValueError("Unexpected template-width formula")
        oldcells = oldtable.findall(W + "tr")[1].findall(W + "tc")
        newcells = newtable.findall(W + "tr")[1].findall(W + "tc")
        if len(oldcells) != 4 or len(newcells) != 4:
            raise ValueError("Unexpected physical row")
        for index in (0, 3):
            for cell, want in ((oldcells[index], 2633), (newcells[index], 2639)):
                props = cell.find(W + "tcPr")
                merge = props.find(W + "vMerge")
                span = props.find(W + "gridSpan")
                if (
                    merge is None
                    or merge.get(W + "val") not in (None, "continue")
                    or span is not None
                    or props.find(W + "tcW").get(W + "w") != str(want)
                ):
                    raise ValueError("Unexpected continuation identity/width")
            newcells[index].find(W + "tcPr/" + W + "tcW").set(W + "w", "2633")
            changes.append({"attribute": f"body/tbl[1]/tr[1]/tc[{index}]/tcW", "old": 2633, "new": 2639})
    if XML.tostring(b, encoding="UTF-8", xml_declaration=True, standalone=True) != before:
        raise ValueError("Unapproved XML after exact inverse")
    return changes


def run(out):
    from wps_ai_agent_cli.docx_styling import qualified_horizontal_print_margins

    out.mkdir(parents=True, exist_ok=False)
    results = {}
    for folder in sorted(BASE.glob("A-*-docx")):
        source = next((folder / "input").glob("*.html"))
        styled = html_styles.load(source, use_browser=True)
        qualification = {
            "mode": styled.mode,
            "browser": styled.browser,
            "print_context": styled.print_context,
            "eligible": qualified_horizontal_print_margins(styled, "editable"),
        }
        parents = {id(c): n for n in _walk(styled.root) for c in n.children if hasattr(c, "tag")}
        qualification["source_images"] = [
            {
                "alt": n.attrs.get("alt", ""),
                "source_align": styled.style(n).get("text-align"),
                "holder_align": styled.style(parents[id(n)]).get("text-align"),
                "holder": parents[id(n)].tag,
            }
            for n in _walk(styled.root)
            if n.tag == "img"
        ]
        (out / (folder.name + "-qualification.json")).write_text(
            json.dumps(qualification, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        if qualification["eligible"] != ("report" not in folder.name):
            raise ValueError("Unexpected eligibility")
        reference = folder / "converted.docx"
        with zipfile.ZipFile(reference) as z:
            infos = {i.filename: copy.copy(i) for i in z.infolist()}
        original_write = zipfile.ZipFile.writestr

        def write_fixed(self, zinfo, data, *args, original_write=original_write, infos=infos, **kwargs):
            name = zinfo.filename if isinstance(zinfo, zipfile.ZipInfo) else zinfo
            return original_write(self, copy.copy(infos[name]), data, *args, **kwargs)

        target = out / (folder.name + ".docx")
        with (
            patch.object(html_styles, "load", return_value=styled),
            patch.object(zipfile.ZipFile, "writestr", write_fixed),
        ):
            converted = convert_html_editable(source, target, use_browser=False)
        if not converted[0]:
            raise ValueError(converted)
        with zipfile.ZipFile(reference) as old, zipfile.ZipFile(target) as new:
            if old.namelist() != new.namelist():
                raise ValueError("Package entries changed")
            allowed = []
            for name in old.namelist():
                a, b = old.read(name), new.read(name)
                if name == "word/document.xml":
                    allowed = verify_document_xml(a, b, folder.name)
                elif a != b:
                    raise ValueError("Unexpected part " + name)
        if "report" in folder.name and reference.read_bytes() != target.read_bytes():
            raise ValueError("Report full bytes differ")
        results[folder.name] = {
            "allowed_changes": allowed,
            "exact_inverse_document_bytes": True,
            "other_parts_identical": True,
            "full_bytes_identical": reference.read_bytes() == target.read_bytes(),
            "candidate_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
        }
        (out / "package-gate.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
        print(folder.name, results[folder.name], flush=True)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    run(args.out)
