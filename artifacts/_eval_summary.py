import json
from pathlib import Path

p = Path(r"C:\Users\admin\AppData\Local\Temp\wps-p4\eval-wps\run-20261014T070755399357Z\summary.json")
d = json.loads(p.read_text(encoding="utf-8"))
print("model", d.get("model"), "cli", d.get("claude_cli"))
print("passed", d.get("passed"), "/", d.get("total"), "skipped", d.get("skipped"))
for r in d["results"]:
    print("==", r["id"], r.get("passes"), "/", r.get("repeat"))
    for i, run in enumerate(r.get("runs") or [], 1):
        a = run.get("agent") or {}
        m = run.get("metrics") or {}
        print(
            " run", i,
            "passed", run.get("passed"),
            "turns", a.get("num_turns"),
            "calls", m.get("wps_tool_calls"),
            "errors", m.get("wps_tool_errors"),
            "ms", a.get("duration_ms"),
        )
        if not run.get("passed"):
            for c in a.get("tool_calls") or []:
                name = str(c.get("name") or "")
                if "wps_agent" in name or name.startswith("mcp__"):
                    print("  ", name, c.get("error_codes"), c.get("is_error"))
