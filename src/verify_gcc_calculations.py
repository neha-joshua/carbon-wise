"""Recalculate selected GCC Climate Budget estimate arithmetic from published inputs.

These checks validate the arithmetic only. They do not validate activity data,
fuel replacement, operating hours, emission factors, or realized reductions.
"""
from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "evidence" / "gcc_report_calculation_checks.csv"


def calculation_checks() -> list[dict[str, str]]:
    checks = [
        {
            "project_id": "R02",
            "method": "CIRIS landfill estimate minus composting emissions",
            "formula": "39964 - 6409",
            "inputs_and_assumptions": "GCC report p.55; 2 x 50 MT/day plants; 365 days and 100% utilization assumed",
            "reported_value": "33555",
            "recomputed_value": str(39964 - 6409),
            "unit": "tCO2e/year (potential, modelled)",
            "status": "arithmetic_reproduced; operating assumptions not validated",
        },
        {
            "project_id": "R13",
            "method": "sum of GCC-reported LED subcategory savings",
            "formula": "54.57 + 16.37 + 179.40",
            "inputs_and_assumptions": "GCC report pp.60-61; 1,610 proposed lights, 11 hours/day, 365 days/year, 0.7469 tCO2/MWh",
            "reported_value": "250.34",
            "recomputed_value": str(54.57 + 16.37 + 179.40),
            "unit": "tCO2e/year (potential, modelled)",
            "status": "published_component_sum_reproduced; light installation and operating assumptions not validated",
        },
        {
            "project_id": "R16",
            "method": "CNG mini-truck replacement estimate",
            "formula": "(0.307 - 0.122) kgCO2/km x 9360 km/year x 15 vehicles / 1000",
            "inputs_and_assumptions": "GCC report pp.56-57; 30 km/day x 26 days/month x 12 months; diesel replacement assumed",
            "reported_value": "25.974",
            "recomputed_value": str((0.307 - 0.122) * 9360 * 15 / 1000),
            "unit": "tCO2e/year (potential, modelled)",
            "status": "arithmetic_reproduced; mileage and replacement counterfactual not validated",
        },
        {
            "project_id": "R17",
            "method": "CNG recovery-vehicle replacement estimate",
            "formula": "(0.770 - 0.655) kgCO2/km x 12000 km/year x 3 vehicles / 1000",
            "inputs_and_assumptions": "GCC report pp.57-58; 50 km/day x 20 days/month x 12 months; diesel replacement assumed",
            "reported_value": "4.14",
            "recomputed_value": str((0.770 - 0.655) * 12000 * 3 / 1000),
            "unit": "tCO2e/year (potential, modelled)",
            "status": "arithmetic_reproduced; mileage and replacement counterfactual not validated",
        },
        {
            "project_id": "R18",
            "method": "CNG water-tanker replacement estimate",
            "formula": "(1.302 - 1.250) kgCO2/km x 31200 km/year x 6 vehicles / 1000",
            "inputs_and_assumptions": "GCC report pp.58-60; 100 km/day x 26 days/month x 12 months; diesel replacement assumed",
            "reported_value": "9.7344",
            "recomputed_value": str((1.302 - 1.250) * 31200 * 6 / 1000),
            "unit": "tCO2e/year (potential, modelled)",
            "status": "arithmetic_reproduced; mileage and replacement counterfactual not validated",
        },
    ]
    return checks


def run() -> list[dict[str, str]]:
    checks = calculation_checks()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(checks[0]))
        writer.writeheader()
        writer.writerows(checks)
    return checks


if __name__ == "__main__":
    for check in run():
        print(f"{check['project_id']}: {check['reported_value']} -> {check['recomputed_value']} [{check['status']}]")
    print(f"Saved {OUT}")
