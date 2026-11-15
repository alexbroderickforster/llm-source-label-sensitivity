"""Figure 1 and Table 1 data for the report, computed from results/results.json (cell_rates).
Pair-level means (averaged over ES/EN; replicates excluded), then mean across the 40 pairs with a
percentile bootstrap CI over pairs (seed 20261114, 10,000 resamples) - same unit as the preregistered tests."""
import json, random
from collections import defaultdict
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
R = json.load(open(ROOT / "results/results.json"))
ARMS = [("A1", "No\nlabels"), ("A6", "Web\naddress"), ("A2", "True\nlabels"), ("A3", "Swapped\nlabels"),
        ("A4", "Score\n2/10"), ("A5", "True +\nnudge")]
MODELS = [("claude-sonnet-5-5", "Claude Sonnet 5.5"), ("gpt-5.4-mini-2026-03-17", "GPT-5.4 mini"),
          ("qwen/qwen3.8-27b", "Qwen3.8 27B"), ("gemini-3.8-flash", "Gemini 3.8 Flash (exploratory)")]
RT, IND = "#2a78d6", "#eb6834"   # validated categorical slots 1-2 (dataviz default palette)


def table():
    acc = defaultdict(lambda: defaultdict(list))
    for c in R["cell_rates"].values():
        if c["pilot"] or c["replicate"]: continue
        for side in ("S", "R"):
            if c[side]["denominator"]:
                acc[(c["model"], c["arm"], side)][c["pair_id"]].append(c[side]["endorsement"])
    out = {}
    rng = random.Random(20261114)
    for k, by_pair in acc.items():
        vals = [sum(v) / len(v) for v in by_pair.values()]
        m = sum(vals) / len(vals)
        boots = sorted(sum(rng.choice(vals) for _ in vals) / len(vals) for _ in range(10000))
        out[k] = (100 * m, 100 * boots[249], 100 * boots[9749], len(vals))
    return out


def figure(t):
    plt.rcParams.update({"font.size": 10, "font.family": "sans-serif", "axes.edgecolor": "#b9b8b2", "axes.linewidth": 0.8})
    fig, axes = plt.subplots(2, 2, figsize=(10, 7.4), sharey=True); axes = axes.ravel()
    xs = range(len(ARMS))
    for ax, (m, name) in zip(axes, MODELS):
        for side, col, lab, dx, fill in (("S", RT, "RT-only claims", -0.12, col_ := True), ("R", IND, "Independent-only claims", 0.12, False)):
            ys = [t[(m, a, side)][0] for a, _ in ARMS]
            lo = [t[(m, a, side)][0] - t[(m, a, side)][1] for a, _ in ARMS]
            hi = [t[(m, a, side)][2] - t[(m, a, side)][0] for a, _ in ARMS]
            ax.errorbar([x + dx for x in xs], ys, yerr=[lo, hi], fmt="o", ms=7, color=col, mfc=col if fill else "white",
                        mew=2, elinewidth=1.4, capsize=0, label=lab, zorder=3)
        base = t[(m, "A1", "S")][0]
        ax.axhline(base, color=RT, lw=0.8, ls=(0, (3, 3)), alpha=0.6, zorder=1)
        ax.set_title(name, fontsize=11, loc="left")
        ax.set_xticks(list(xs)); ax.set_xticklabels([l for _, l in ARMS], fontsize=9)
        ax.grid(axis="y", color="#e6e5e0", lw=0.8); ax.set_axisbelow(True)
        for s in ("top", "right"): ax.spines[s].set_visible(False)
        ax.set_ylim(0, 80)
    fig.supylabel("% of claims stated as fact (lower = less repeated)", fontsize=10)
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, loc="upper center", ncol=2, frameon=False, bbox_to_anchor=(0.5, 1.0))
    fig.tight_layout(rect=(0.01, 0, 1, 0.95), h_pad=2.0)
    for ext in ("png", "pdf"):
        fig.savefig(ROOT / f"report/figure1.{ext}", dpi=220)


if __name__ == "__main__":
    t = table()
    figure(t)
    rows = {f"{m}|{a}|{s}": v for (m, a, s), v in t.items()}
    json.dump(rows, open(ROOT / "report/figure1_data.json", "w"), indent=1)
    for m, name in MODELS:
        print(name)
        for a, lab in [("A0", "Reference only")] + ARMS:
            s = t.get((m, a, "S")); r = t.get((m, a, "R"))
            print(f"  {lab.replace(chr(10),' '):24s} RT-only {s[0]:5.1f} [{s[1]:.1f},{s[2]:.1f}]   indep-only {r[0]:5.1f}" if s else f"  {lab}: RT n/a; indep {r[0]:.1f}")
