# Original manual: horizontal-rule spacing evidence

See [acceptance and limitations](../../docs/FIDELITY_STAGE7_ACCEPTANCE.md).
`comparison.json` records exact versions, hashes, positions, fixed-region SSIM
and the six local gates. `manual/` contains original input and generated outputs;
before evidence is the committed Stage 4 manual case. Original fixture bytes and
thresholds are unchanged. Whole-case strict F2 still fails at 0.8959.

Reproduce from the repository root with the test/browser/WPS dependencies installed:

```powershell
python scripts/manual_rule_evidence.py --out artifacts/manual-rule-spacing-rerun
```

Use a new output directory and no existing WPS instance. Only the runner's own
conversion instance is released. The archived input alone has `-text` attributes
to keep its SHA-256 independent of checkout line-ending conversion.
