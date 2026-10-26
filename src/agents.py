"""
agents.py

Rule-based summaries of the generated sample-model comparison. These are not
autonomous AI agents or evidence of real-world outcomes.
"""
import pandas as pd


def carbon_agent_statement(comparison: pd.DataFrame) -> str:
    best = comparison.loc[comparison["carbon_score"].idxmax()]
    cw = comparison[comparison["method"].str.contains("CarbonWise")].iloc[0]
    if best["method"] == cw["method"]:
        return f"In this sample comparison, the selected plan has the highest carbon score ({cw['carbon_score']:.0f}) among the methods shown. This score is not a measured emissions reduction."
    gap = best["carbon_score"] - cw["carbon_score"]
    return (f"In this sample comparison, {best['method']} has the highest carbon score ({best['carbon_score']:.0f}), "
            f"{gap:.0f} points above the selected plan's {cw['carbon_score']:.0f}. These are relative model scores, not physical reductions.")


def resilience_agent_statement(comparison: pd.DataFrame) -> str:
    cw = comparison[comparison["method"].str.contains("CarbonWise")].iloc[0]
    others = comparison[~comparison["method"].str.contains("CarbonWise")]
    max_other = others["resilience_score"].max()
    lift = (cw["resilience_score"] - max_other) / max_other * 100 if max_other > 0 else 0
    return (f"The selected sample plan's resilience score is {cw['resilience_score']:.0f}; "
            f"that is {lift:.0f}% above the next-highest comparison score. It does not measure flood or heat protection.")


def equity_agent_statement(comparison: pd.DataFrame) -> str:
    cw = comparison[comparison["method"].str.contains("CarbonWise")].iloc[0]
    others = comparison[~comparison["method"].str.contains("CarbonWise")]
    max_other = others["equity_score"].max()
    lift = (cw["equity_score"] - max_other) / max_other * 100 if max_other > 0 else 0
    return (f"The selected sample plan's community score is {cw['equity_score']:.0f}, "
            f"{lift:.0f}% above the highest comparison score. This relative score does not show who received benefits or prove an equity outcome.")


def budget_agent_statement(comparison: pd.DataFrame, budget_cr: float) -> str:
    cw = comparison[comparison["method"].str.contains("CarbonWise")].iloc[0]
    pct = cw["total_cost_cr"] / budget_cr * 100
    return (f"The sample plan uses Rs {cw['total_cost_cr']:.1f} crore of the "
            f"Rs {budget_cr:.1f} crore limit ({pct:.0f}%) across "
            f"{int(cw['n_projects'])} generated examples.")


def coordinator_statement(comparison: pd.DataFrame) -> str:
    cw = comparison[comparison["method"].str.contains("CarbonWise")].iloc[0]
    return (f"The selected sample plan balances three relative model scores: carbon "
            f"{cw['carbon_score']:.0f}, resilience {cw['resilience_score']:.0f}, and community "
            f"{cw['equity_score']:.0f}. The search returns options; it does not prove real-world benefits or guarantee every possible plan was found.")


def full_council_report(comparison: pd.DataFrame, budget_cr: float) -> list[dict]:
    return [
        {"agent": "Carbon score", "statement": carbon_agent_statement(comparison)},
        {"agent": "Resilience score", "statement": resilience_agent_statement(comparison)},
        {"agent": "Community score", "statement": equity_agent_statement(comparison)},
        {"agent": "Budget", "statement": budget_agent_statement(comparison, budget_cr)},
        {"agent": "Summary", "statement": coordinator_statement(comparison)},
    ]
