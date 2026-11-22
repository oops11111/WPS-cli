"""Measure the disposable char-range candidate against launch's same-canvas WPS baseline."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from html_pptx_stage0_audit import _writable_mkdtemp

from wps_ai_agent_cli.fidelity import fidelity_check

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "fixtures/html_complex/launch.html"
CANDIDATE = ROOT / "artifacts/html-pptx-inline-stage4-20261122/launch-char-range-candidate.pptx"
BASELINE = ROOT / "artifacts/html-pptx-stage3-20261122/manifest.json"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    if out.exists() and any(out.iterdir()):
        parser.error("output directory must be empty")
    out.mkdir(parents=True, exist_ok=True)
    tempfile.mkdtemp = _writable_mkdtemp
    ok, report, errors = fidelity_check(SOURCE, CANDIDATE, renderer="wps", images_dir=out / "pages")
    if not ok:
        raise RuntimeError(errors)
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))["cases"]["A-launch-pptx"]
    current = report["aspects"]["layout"]
    prior = baseline["fidelity"]["aspects"]["layout"]
    result = {
        "candidate_page_scores": current["page_scores"],
        "baseline_page_scores": prior["page_scores"],
        "page_score_delta": [
            round(now - old, 4) for now, old in zip(current["page_scores"], prior["page_scores"], strict=True)
        ],
        "candidate_aggregate": current["score"],
        "baseline_aggregate": prior["score"],
        "semantic_aspects": {
            name: aspect.get("score")
            for name, aspect in report["aspects"].items()
            if name in {"text", "structure", "formatting", "animations", "data"}
        },
        "report": report,
    }
    (out / "static_report.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "report"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
