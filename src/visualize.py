"""
visualize.py
Generates the two figures you'll want for your Review-2 PPT:
1. Pareto front scatter (carbon vs resilience, colored by equity)
2. Baseline comparison bar chart (Equal Split vs Greedy vs CarbonWise)
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

plt.rcParams["font.family"] = "serif"
plt.rcParams["font.serif"] = ["Times New Roman", "Times", "DejaVu Serif"]

from preprocessing import preprocess
from equity_scoring import compute_equity_score
from optimizer import run_nsga2, pareto_front_to_df, pick_balanced_solution
from baselines import (equal_split_allocation, greedy_cost_effectiveness_allocation,
                        summarize_portfolio)

FIG_DIR = "../results/figures"

df = preprocess()
df = compute_equity_score(df)
BUDGET_CR = 50.0

res, problem = run_nsga2(df, BUDGET_CR)
front_df = pareto_front_to_df(res, problem, df)
balanced = pick_balanced_solution(front_df)

# --- Figure 1: Pareto front ---
fig, ax = plt.subplots(figsize=(8, 6))
sc = ax.scatter(front_df["carbon_score"], front_df["resilience_score"],
                 c=front_df["equity_score"], cmap="viridis", s=60, alpha=0.85,
                 edgecolors="white", linewidths=0.5)
ax.scatter([balanced["carbon_score"]], [balanced["resilience_score"]],
           marker="*", s=500, color="red", edgecolors="black", linewidths=1,
           label="Recommended balanced portfolio", zorder=5)
cbar = plt.colorbar(sc)
cbar.set_label("Equity Score", fontsize=11)
ax.set_xlabel("Carbon Reduction Score", fontsize=12)
ax.set_ylabel("Resilience Score", fontsize=12)
ax.set_title(f"CarbonWise: NSGA-II Pareto Front (Budget = \u20b9{BUDGET_CR} cr, {len(df)} candidate projects)",
             fontsize=12)
ax.legend()
plt.tight_layout()
plt.savefig(f"{FIG_DIR}/pareto_front.png", dpi=150)
print(f"Saved {FIG_DIR}/pareto_front.png")

# --- Figure 2: Baseline comparison bar chart ---
eq_mask = equal_split_allocation(df, BUDGET_CR)
greedy_mask = greedy_cost_effectiveness_allocation(df, BUDGET_CR)
cw_ids = balanced["selected_projects"].split(";")
cw_mask = df["project_id"].isin(cw_ids)

results = [
    summarize_portfolio(df, eq_mask, "Equal Split"),
    summarize_portfolio(df, greedy_mask, "Greedy\n(Cost-Effectiveness)"),
    summarize_portfolio(df, cw_mask, "CarbonWise\n(NSGA-II)"),
]
comp = pd.DataFrame(results)

fig, ax = plt.subplots(figsize=(9, 6))
x = range(len(comp))
width = 0.25
metrics = ["carbon_score", "resilience_score", "equity_score"]
colors = ["#2C5F2D", "#1C7293", "#B85042"]
labels = ["Carbon", "Resilience", "Equity"]

for i, (metric, color, label) in enumerate(zip(metrics, colors, labels)):
    offset = (i - 1) * width
    ax.bar([xi + offset for xi in x], comp[metric], width, label=label, color=color)

ax.set_xticks(list(x))
ax.set_xticklabels(comp["method"])
ax.set_ylabel("Score (summed, normalized 0-100 per project)", fontsize=11)
ax.set_title("Portfolio Comparison: Equal Split vs Greedy vs CarbonWise", fontsize=13)
ax.legend()
plt.tight_layout()
plt.savefig(f"{FIG_DIR}/baseline_comparison.png", dpi=150)
print(f"Saved {FIG_DIR}/baseline_comparison.png")
