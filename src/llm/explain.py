"""
llm/explain.py

Generates a natural-language explanation of a recommended portfolio.

DESIGN PRINCIPLE (the one that matters most): the LLM is given ONLY the
already-computed, verified numbers from the optimizer -- never raw project
data, never asked to invent or estimate anything. It explains evidence that
already exists; it does not produce new numbers. If the LLM call fails for
ANY reason (no API key, no internet, rate limit, timeout, malformed
response), this silently and immediately falls back to the existing
tested rule-based logic in agents.py. The caller (the dashboard) cannot
tell which path was used except via the `source` field in the return value
-- which IS shown in the UI, for transparency, but the explanation quality
degrades gracefully rather than the app breaking.
"""
from . import client as llm_client
from agents import full_council_report


SYSTEM_PROMPT = """You are an explanation layer for CarbonWise, a municipal \
infrastructure investment decision-support tool. You will be given ONLY \
verified, already-computed numbers from a multi-objective optimizer \
(NSGA-II) and a rule-based comparison against baseline allocation methods.

Your job is strictly to EXPLAIN this evidence in clear, professional \
prose suitable for a city planner or budget committee. You must:
- Use ONLY the numbers given to you. Never invent, estimate, or guess any \
  number not explicitly provided.
- Never recommend a different portfolio than the one described -- your job \
  is to explain the given recommendation, not second-guess the optimizer.
- Keep the explanation to 4-6 sentences, in a neutral, evidence-based tone.
- If asked something the provided data cannot answer, say so plainly \
  rather than speculating.
"""


def _build_user_prompt(context: dict) -> str:
    lines = ["Here is the verified data for the recommended portfolio:\n"]
    for key, val in context.items():
        lines.append(f"- {key}: {val}")
    lines.append(
        "\nWrite a short, professional explanation of why this portfolio was "
        "recommended, what trade-offs it makes relative to the baseline methods, "
        "and what its main risk or limitation is."
    )
    return "\n".join(lines)


def _rule_based_fallback(comparison, budget_cr: float) -> str:
    """Reuses the existing tested agents.py logic -- our reliable fallback."""
    council = full_council_report(comparison, budget_cr)
    return " ".join(entry["statement"] for entry in council)


def generate_explanation(context: dict, comparison, budget_cr: float) -> dict:
    """
    Returns {"text": str, "source": "llm" | "rule_based", "error": str|None}
    Never raises -- always returns something usable.
    """
    if llm_client.is_available():
        try:
            client = llm_client.get_client()
            if client is not None:
                response = client.chat.completions.create(
                    model=llm_client.get_model(),
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": _build_user_prompt(context)},
                    ],
                    temperature=0.3,
                    max_tokens=300,
                    timeout=15,
                )
                text = response.choices[0].message.content.strip()
                if text:
                    return {"text": text, "source": "llm", "error": None}
        except Exception as e:
            # Any failure (no internet, bad key, rate limit, timeout, etc.)
            # falls straight through to the rule-based path below.
            fallback_text = _rule_based_fallback(comparison, budget_cr)
            return {"text": fallback_text, "source": "rule_based",
                    "error": f"LLM call failed ({type(e).__name__}); used rule-based fallback."}

    # No API key configured at all -- expected path for most demo runs.
    fallback_text = _rule_based_fallback(comparison, budget_cr)
    return {"text": fallback_text, "source": "rule_based", "error": None}
