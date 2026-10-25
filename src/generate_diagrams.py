"""
generate_diagrams.py
Produces two PPT-ready figures: the system architecture diagram and the
methodology flowchart, matching the real modules in this codebase (not an
aspirational diagram -- every box corresponds to an actual .py file).
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

plt.rcParams["font.family"] = "serif"
plt.rcParams["font.serif"] = ["Times New Roman", "Times", "DejaVu Serif"]

FOREST = "#0F4C3A"
INK = "#1A2B22"
LINE = "#DDE5E0"
GOLD = "#B8860B"
LIGHT = "#F4F7F5"

def box(ax, x, y, w, h, text, fc=LIGHT, ec=FOREST, fontsize=10, fontweight="normal", textcolor=INK):
    b = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08",
                        linewidth=1.4, edgecolor=ec, facecolor=fc, zorder=2)
    ax.add_patch(b)
    ax.text(x + w/2, y + h/2, text, ha="center", va="center", fontsize=fontsize,
             fontweight=fontweight, color=textcolor, zorder=3, wrap=True)
    return (x + w/2, y), (x + w/2, y + h)  # bottom-center, top-center

def arrow(ax, p1, p2, color=FOREST):
    a = FancyArrowPatch(p1, p2, arrowstyle="-|>", mutation_scale=14,
                         linewidth=1.4, color=color, zorder=1)
    ax.add_patch(a)

# ---------------------------------------------------------------------------
# Figure 1: System Architecture
# ---------------------------------------------------------------------------
import pandas as pd
_wards_count = len(pd.read_csv("../data/raw/wards.csv"))
_projects_count = len(pd.read_csv("../data/raw/projects.csv"))

fig, ax = plt.subplots(figsize=(9, 11))
ax.set_xlim(0, 10)
ax.set_ylim(0, 16)
ax.axis("off")

ax.text(5, 15.5, "CarbonWise System Architecture", ha="center", fontsize=16,
         fontweight="bold", color=INK)

# Layer 1: Raw data
_, top1 = box(ax, 2, 13.8, 6, 1.0, f"Raw Data Input\nwards.csv ({_wards_count} zones)  +  projects.csv ({_projects_count} projects)",
              fc="#EAF2ED", fontsize=9.5)

# Layer 2: preprocessing
bot2, top2 = box(ax, 2.5, 12.2, 5, 0.9, "preprocessing.py\nJoin, clean, normalise metrics", fontsize=9.5)
arrow(ax, (5, 13.8), (5, 13.1))

# Layer 3: scoring engines (3 parallel)
b3a = box(ax, 0.7, 10.6, 2.6, 0.9, "carbon_scoring\n(in preprocessing.py)", fontsize=8.5)
b3b = box(ax, 3.7, 10.6, 2.6, 0.9, "resilience_scoring\n(in preprocessing.py)", fontsize=8.5)
b3c = box(ax, 6.7, 10.6, 2.6, 0.9, "equity_scoring.py", fontsize=8.5)
for bx in [2.0, 5.0, 8.0]:
    arrow(ax, (5, 12.2), (bx, 11.5))

# data validation checkpoint
bot_v, top_v = box(ax, 3.2, 9.2, 3.6, 0.7, "data_validation.py\nintegrity check", fc="#FBF7EC", ec=GOLD, fontsize=8.5)
arrow(ax, (2.0, 10.6), (5, 9.9))
arrow(ax, (5.0, 10.6), (5, 9.9))
arrow(ax, (8.0, 10.6), (5, 9.9))

# User inputs
_, top_u = box(ax, 6.8, 9.2, 2.6, 0.7, "User Inputs\nBudget, equity weights", fc="#EFF3FF", fontsize=8.5)

# NSGA-II
_, top_n = box(ax, 1.5, 7.6, 7, 1.1,
               "optimizer.py \u2014 NSGA-II Multi-Objective Engine\nMaximise: Carbon + Resilience + Equity   |   Subject to: Cost \u2264 Budget",
               fc="#0F4C3A", ec=INK, fontsize=9.5, fontweight="bold", textcolor="white")
arrow(ax, (5, 9.2), (5, 8.7))
arrow(ax, (8.1, 9.2), (7.5, 8.7))

# Pareto front + balanced selection
_, top_p = box(ax, 2.5, 6.2, 5, 0.9, "Pareto Front  \u2192  pick_balanced_solution()\n(ideal-point distance method)", fontsize=9)
arrow(ax, (5, 7.6), (5, 7.1))

# Three analysis branches
b6a = box(ax, 0.3, 4.6, 2.9, 0.9, "baselines.py\nEqual Split, Greedy", fontsize=8.5)
b6b = box(ax, 3.55, 4.6, 2.9, 0.9, "equity_auditor.py\nInvestment-share audit", fontsize=8.5)
b6c = box(ax, 6.8, 4.6, 2.9, 0.9, "scenarios.py +\nsensitivity.py", fontsize=8.5)
for bx in [1.75, 5.0, 8.25]:
    arrow(ax, (5, 6.2), (bx, 5.5))

# decision rationale + explanation layer
bot_r, top_r = box(ax, 1.5, 3.0, 7, 0.9,
                    "decision_rationale.py  +  agents.py  (rule-based, deterministic)\noptional: llm/explain.py (AI upgrade, safe fallback)",
                    fc="#FBF7EC", ec=GOLD, fontsize=8.5)
for bx in [1.75, 5.0, 8.25]:
    arrow(ax, (bx, 4.6), (5, 3.9))

# Dashboard
box(ax, 2, 1.2, 6, 1.0, "Streamlit Dashboard\nInteractive decision-support interface", fc="#0F4C3A",
    ec=INK, fontsize=10, fontweight="bold", textcolor="white")
arrow(ax, (5, 3.0), (5, 2.2))

plt.tight_layout()
plt.savefig("../results/figures/architecture_diagram.png", dpi=180, bbox_inches="tight")
print("Saved architecture_diagram.png")
plt.close()

# ---------------------------------------------------------------------------
# Figure 2: Methodology flowchart (linear, phase-based)
# ---------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(4.5, 11))
ax.set_xlim(0, 6)
ax.set_ylim(0, 17)
ax.axis("off")
ax.text(3, 16.5, "CarbonWise Methodology", ha="center", fontsize=14, fontweight="bold", color=INK)

phases = [
    ("Phase 1", "Data Collection", "Chennai zones (Nandhini et al. 2025) +\nproject benchmarks (MNRE, CEA, CPHEEO)"),
    ("Phase 2", "Data Processing", "Clean, join, normalise\n(preprocessing.py)"),
    ("Phase 3", "Scoring", "Carbon / Resilience / Equity\nscores per project"),
    ("Phase 4", "Validation", "Automated data-quality\ncheck before optimisation"),
    ("Phase 5", "Optimisation", "NSGA-II generates the\nPareto-optimal frontier"),
    ("Phase 6", "Evaluation", "Compare vs. Equal-Split\nand Greedy baselines"),
    ("Phase 7", "Equity Audit", "Investment-share vs.\npopulation-share analysis"),
    ("Phase 8", "Decision Support", "Rationale + scenarios +\nsensitivity + dashboard"),
]

y = 15.3
for i, (label, title, detail) in enumerate(phases):
    box(ax, 0.4, y - 1.05, 5.2, 1.3, f"{label}: {title}\n{detail}", fontsize=8.7)
    if i < len(phases) - 1:
        arrow(ax, (3, y - 1.05), (3, y - 1.6))
    y -= 1.9

plt.tight_layout()
plt.savefig("../results/figures/methodology_flowchart.png", dpi=180, bbox_inches="tight")
print("Saved methodology_flowchart.png")
