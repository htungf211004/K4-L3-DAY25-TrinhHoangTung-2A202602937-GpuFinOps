"""Report assembly — the lab's deliverable: baseline vs optimized + savings chart."""
from __future__ import annotations


def build_report(baseline_usd: float, optimized_usd: float, levers: dict,
                 sustainability: dict | None = None, period: str = "monthly") -> str:
    """Return a markdown cost-optimization report."""
    savings = baseline_usd - optimized_usd
    pct = (savings / baseline_usd * 100.0) if baseline_usd > 0 else 0.0
    lines = [
        "# NimbusAI — GPU Cost Optimization Report",
        "",
        f"**Period:** {period}  ",
        f"**Baseline spend:** ${baseline_usd:,.0f}  ",
        f"**Optimized spend:** ${optimized_usd:,.0f}  ",
        f"**Projected savings:** ${savings:,.0f}  (**{pct:.0f}%**)",
        "",
        "## Savings by lever",
        "",
        "| Lever | Savings (USD) |",
        "|---|---|",
    ]
    for name, amount in levers.items():
        lines.append(f"| {name} | ${amount:,.0f} |")
    if sustainability:
        lines += [
            "",
            "## Sustainability",
            "",
            f"- Energy per query: {sustainability.get('wh_per_query', 0):.2f} Wh",
            f"- Carbon per query: {sustainability.get('carbon_g', 0):.3f} gCO2e",
            f"- Cleanest region: {sustainability.get('best_region', 'n/a')}",
            f"- Cheapest electricity region: {sustainability.get('cheapest_region', 'n/a')}",
        ]
    lines += ["", "_Figures are June-2026 as-of snapshots; re-baseline before acting._"]
    return "\n".join(lines)


def savings_waterfall(levers: dict, path: str, baseline_usd: float | None = None) -> str:
    """Write savings bars, or a cumulative waterfall when baseline is supplied."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return ""
    names = list(levers.keys())
    vals = [levers[n] for n in names]
    fig, ax = plt.subplots(figsize=(11, 5.5))
    if baseline_usd is None:
        ax.bar(names, vals, color="#2e548a")
        ax.set_ylabel("Savings (USD / month)")
    else:
        remaining = baseline_usd
        labels = ["Baseline"] + names + ["Optimized"]
        heights, bottoms = [baseline_usd], [0]
        annotations = [f"${baseline_usd:,.0f}"]
        for amount in vals:
            remaining -= amount
            heights.append(amount)
            bottoms.append(remaining)
            annotations.append(f"-${amount:,.0f}")
        heights.append(remaining)
        bottoms.append(0)
        annotations.append(f"${remaining:,.0f}")
        ax.bar(range(len(labels)), heights, bottom=bottoms,
               color=["#2e548a"] + ["#36876a"] * len(vals) + ["#2e548a"])
        for i, (height, bottom, annotation) in enumerate(zip(heights, bottoms, annotations)):
            ax.text(i, bottom + height + baseline_usd * 0.018, annotation,
                    ha="center", fontsize=9)
            if i < len(labels) - 1:
                level = baseline_usd if i == 0 else bottom
                ax.plot([i + 0.4, i + 0.6], [level, level], color="#777777", linewidth=1)
        ax.set_xticks(range(len(labels)), labels)
        ax.set_ylim(0, baseline_usd * 1.12)
        ax.set_ylabel("Spend (USD / 30-day scenario)")
    ax.set_title("NimbusAI - projected GPU cost savings")
    ax.grid(axis="y", alpha=0.2)
    ax.set_axisbelow(True)
    plt.xticks(rotation=18, ha="right", fontsize=9)
    plt.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)
    return path
