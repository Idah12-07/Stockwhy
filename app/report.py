"""Plain-language report. Every number comes from the result dict (no canned text per case)."""


def render(result):
    q = result["question"]
    lines = [f"# Why did {q['facility_id']} run out of {q['commodity']} in {q['month']}?", ""]
    if result["status"] == "nothing_to_investigate":
        return "\n".join(lines + [result["reason"]])
    v = result["verdict"]
    lines += [f"Reported stock-out: {result['plan']['reported_stockout_days']} day(s). Confidence: **{v['confidence']}**."
              + (" Evidence was re-checked once over a wider window." if result["revised"] else ""), ""]
    if v["escalate"]:
        lines += ["**Escalated to a human:** the evidence does not clearly explain this stock-out. No action drafted.", ""]
    lines += ["## Ranked causes (evidence-weighted estimates, not statistics)", "",
              "| # | Cause | Share | Strength |", "|---|---|---|---|"]
    for i, r in enumerate(v["ranked"], 1):
        lines.append(f"| {i} | {r['name']} | {r['weight']:.0%} | {r['score']:.2f} |")
    lines += ["", "## Evidence", ""]
    for r in v["ranked"][:3]:
        if r["score"] <= 0.05:
            continue
        cites = f" [{', '.join(r['citations'])}]" if r["citations"] else ""
        lines.append(f"**{r['name']}**")
        lines += [f"- {f}" for f in r["findings"]]
        if cites:
            lines.append(f"- Sources:{cites}")
        lines.append("")
    ruled = [r["name"] for r in v["ranked"] if r["score"] <= 0.05]
    if ruled:
        lines += [f"Ruled out or no evidence: {', '.join(ruled)}.", ""]
    a = result["action"]
    if a:
        lines += ["## Draft action (needs human approval)", "", a["memo"], "", f"Process fix: {a['process_fix']}", ""]
    mem = result.get("memory")
    if mem:
        lines += ["## Case memory (Meterless H-MEM)", ""]
        if mem.get("note"):
            lines.append(mem["note"])
        elif mem["prior_cases"]:
            lines.append(f"{len(mem['prior_cases'])} earlier case(s) for this facility and medicine: " + "; ".join(f"{c['month']} {c['cause']} ({c['memory_id']})" for c in mem["prior_cases"]) + ".")
            if mem["repeat_issue"]:
                lines.append("**This is a repeat issue:** the same cause was found before.")
        else:
            lines.append("No earlier cases remembered for this facility and medicine. This case is now stored.")
        lines.append("")
    lines += [f"_Run time: {result['seconds']}s. Data is synthetic. Contribution shares are estimates._"]
    return "\n".join(lines)
