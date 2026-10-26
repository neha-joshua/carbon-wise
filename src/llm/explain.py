"""
llm/explain.py

Optional natural-language summary of scores from generated sample projects.
It does not verify source data or real-world impacts. A failed LLM call uses
a rule-based summary, and the UI labels that fallback.
"""
from . import client as llm_client
from agents import full_council_report


SYSTEM_PROMPT = """You explain outputs from CarbonWise's generated sample-project \
planner. The provided values are model scores and comparisons from synthetic \
examples; they are not independently verified or observed city outcomes.

Your job is strictly to EXPLAIN this evidence in clear, professional \
prose suitable for a city planner or budget committee. You must:
- Use ONLY the numbers given to you. Never invent, estimate, or guess any \
  number not explicitly provided.
- Call carbon, resilience, and community values relative model scores. Do not \
  describe them as tonnes of emissions, flood protection, or delivered benefits.
- Do not claim that a project caused an outcome or that residents received a benefit.
- Never recommend a different portfolio than the one described -- your job \
  is to explain the given recommendation, not second-guess the optimizer.
- Keep the explanation to 4-6 sentences, in a neutral, evidence-based tone.
- If asked something the provided data cannot answer, say so plainly \
  rather than speculating.
"""


def _build_user_prompt(context: dict) -> str:
    lines = ["Here are the generated sample-model values for the selected plan:\n"]
    for key, val in context.items():
        lines.append(f"- {key}: {val}")
    lines.append(
        "\nWrite a short explanation of why this plan was selected, what trade-offs "
        "it makes compared with the listed methods, and one important limitation. "
        "State that these are relative model scores from generated examples, not "
        "measured real-world impacts."
    )
    return "\n".join(lines)


def _rule_based_fallback(comparison, budget_cr: float) -> str:
    """Build a rule-based fallback from the sample-model comparisons."""
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
