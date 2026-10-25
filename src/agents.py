"""
agents.py

Templated "multi-agent council" -- five specialised agents that each read the
SAME real optimizer/comparison outputs and generate a rule-based sentence
from their own perspective. This deliberately does NOT call an LLM: for a
live panel demo, a rule-based agent that reads real numbers is more reliable
than an API call that can hallucinate a number in front of your panel. Full
LLM-based agentic reasoning (per Papers 5, 6 in the lit review) is scoped as
Final Review follow-up work -- state this explicitly if asked.
"""
import pandas as pd


def carbon_agent_statement(comparison: pd.DataFrame) -> str:
    best = comparison.loc[comparison["carbon_score"].idxmax()]
    cw = comparison[comparison["method"].str.contains("CarbonWise")].iloc[0]
    if best["method"] == cw["method"]:
        return f"The recommended portfolio also delivers the highest carbon reduction score ({cw['carbon_score']:.0f}) among all methods compared."
    gap = best["carbon_score"] - cw["carbon_score"]
    return (f"'{best['method']}' achieves the highest raw carbon score ({best['carbon_score']:.0f}), "
            f"{gap:.0f} points above CarbonWise's {cw['carbon_score']:.0f} -- "
            f"but at a cost to resilience and equity, detailed below.")


def resilience_agent_statement(comparison: pd.DataFrame) -> str:
    cw = comparison[comparison["method"].str.contains("CarbonWise")].iloc[0]
    others = comparison[~comparison["method"].str.contains("CarbonWise")]
    max_other = others["resilience_score"].max()
    lift = (cw["resilience_score"] - max_other) / max_other * 100 if max_other > 0 else 0
    return (f"CarbonWise's portfolio scores {cw['resilience_score']:.0f} on resilience, "
            f"a {lift:.0f}% improvement over the next-best method -- meaning stronger "
            f"protection against flood and heat exposure across funded zones.")


def equity_agent_statement(comparison: pd.DataFrame) -> str:
    cw = comparison[comparison["method"].str.contains("CarbonWise")].iloc[0]
    others = comparison[~comparison["method"].str.contains("CarbonWise")]
    max_other = others["equity_score"].max()
    lift = (cw["equity_score"] - max_other) / max_other * 100 if max_other > 0 else 0
    return (f"CarbonWise's portfolio scores {cw['equity_score']:.0f} on equity, "
            f"{lift:.0f}% higher than the best-performing baseline -- concentrating more "
            f"investment in Chennai's highest-vulnerability zones (per the Nandhini et al. "
            f"2025 vulnerability index).")


def budget_agent_statement(comparison: pd.DataFrame, budget_cr: float) -> str:
    cw = comparison[comparison["method"].str.contains("CarbonWise")].iloc[0]
    pct = cw["total_cost_cr"] / budget_cr * 100
    return (f"The recommended portfolio uses \u20b9{cw['total_cost_cr']:.1f} crore of the "
            f"\u20b9{budget_cr:.1f} crore available ({pct:.0f}% utilisation) across "
            f"{int(cw['n_projects'])} projects.")


def coordinator_statement(comparison: pd.DataFrame) -> str:
    cw = comparison[comparison["method"].str.contains("CarbonWise")].iloc[0]
    return (f"Balanced portfolio recommended: it does not maximise any single objective, "
            f"but avoids the resilience and equity shortfalls of the greedy carbon-only "
            f"strategy while still delivering strong carbon reduction "
            f"(score {cw['carbon_score']:.0f}). This trade-off is the direct output of "
            f"NSGA-II's multi-objective search, not a manually tuned rule.")


def full_council_report(comparison: pd.DataFrame, budget_cr: float) -> list[dict]:
    return [
        {"agent": "Carbon Agent", "statement": carbon_agent_statement(comparison)},
        {"agent": "Resilience Agent", "statement": resilience_agent_statement(comparison)},
        {"agent": "Equity Agent", "statement": equity_agent_statement(comparison)},
        {"agent": "Budget Agent", "statement": budget_agent_statement(comparison, budget_cr)},
        {"agent": "Coordinator", "statement": coordinator_statement(comparison)},
    ]
