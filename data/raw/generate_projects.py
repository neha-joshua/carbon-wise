"""
Generates projects.csv: a set of candidate infrastructure interventions for
Chennai's 15 GCC zones, with cost / carbon-reduction / resilience-benefit
figures grounded in published benchmark ranges.

BENCHMARK SOURCES (verify exact figures against these before final submission
-- these are defensible order-of-magnitude anchors, not claimed-precise values):
  - Solar rooftop cost & yield: MNRE (Ministry of New & Renewable Energy)
    rooftop solar benchmark cost circular; India solar irradiance ~1,400-1,600
    kWh/kWp/year for Chennai.
  - Grid emission factor: Central Electricity Authority (CEA) CO2 Baseline
    Database, All-India combined margin emission factor (~0.7-0.8 tCO2/MWh
    in recent editions -- use the latest CEA release for your report).
  - Building retrofit / LED retrofit costs: Bureau of Energy Efficiency (BEE)
    UJALA / municipal energy-efficiency program benchmarks.
  - Drainage/stormwater upgrade costs: CPHEEO (Central Public Health &
    Environmental Engineering Organisation) manual on storm water drainage.
  - Urban tree planting cost & sequestration: MoEFCC / Smart Cities Mission
    green-infrastructure guidelines; IPCC AR6 WG3 nature-based sequestration
    ranges.
  - Public transit (bus electrification): FAME-II / CESL electric bus
    procurement cost benchmarks; carbon savings from replacing diesel BS-IV
    buses with electric.
  - Flood barrier / embankment costs: Tamil Nadu PWD / GCC capital works
    schedule of rates (indicative).
  - EV charging infrastructure cost & impact: Tamil Nadu EV Policy 2019 +
    FAME-II charging-infrastructure subsidy benchmarks; emissions offset
    estimated from displaced two/three-wheeler and bus-fleet fuel use.

Each project row also carries the zone it serves, so equity scoring can pull
in that zone's vulnerability index from wards.csv.
"""
import pandas as pd
import numpy as np

rng = np.random.default_rng(42)  # reproducible

wards = pd.read_csv("wards.csv")
zone_ids = wards["zone_id"].tolist()

# category: (cost_lakhs_range, carbon_tco2_per_year_range, resilience_0_100_range, base_pop_benefited_range)
CATEGORIES = {
    "Solar Rooftop (public building)":      ((15, 60),   (25, 90),   (10, 30),  (500, 3000)),
    "Building Retrofit (LED+insulation)":   ((10, 40),   (15, 60),   (20, 45),  (500, 4000)),
    "Stormwater Drainage Upgrade":          ((150, 600), (2, 10),    (70, 98),  (5000, 40000)),
    "Urban Tree Canopy / Green Corridor":   ((8, 35),    (10, 40),   (35, 65),  (2000, 20000)),
    "Public Transit Electrification (bus)": ((300, 1200),(120, 400), (40, 70),  (20000, 150000)),
    "Flood Barrier / Embankment":           ((200, 800), (1, 5),     (75, 99),  (8000, 60000)),
    "Cool Roof / Reflective Pavement":      ((5, 20),    (5, 20),    (25, 50),  (1000, 8000)),
    "EV Charging Hub (public/transit)":     ((20, 90),   (18, 55),   (15, 35),  (3000, 25000)),
}

N_PROJECTS = 56
rows = []
categories = list(CATEGORIES.keys())

for i in range(N_PROJECTS):
    cat = categories[i % len(categories)]
    (cost_lo, cost_hi), (carb_lo, carb_hi), (res_lo, res_hi), (pop_lo, pop_hi) = CATEGORIES[cat]
    zone = zone_ids[rng.integers(0, len(zone_ids))]
    zone_row = wards[wards.zone_id == zone].iloc[0]

    cost = round(rng.uniform(cost_lo, cost_hi), 1)
    carbon = round(rng.uniform(carb_lo, carb_hi), 1)
    resilience = round(rng.uniform(res_lo, res_hi), 1)

    # projects in higher-vulnerability zones plausibly serve a higher share
    # of at-risk population -- scale population-benefited slightly with zone vulnerability
    pop_base = rng.uniform(pop_lo, pop_hi)
    pop_benefited = int(pop_base * (0.7 + 0.6 * zone_row["vulnerability_index"]))
    pop_benefited = min(pop_benefited, int(zone_row["approx_population_2023"]))

    rows.append({
        "project_id": f"P{i+1:03d}",
        "project_name": f"{cat} - {zone_row['zone_name']}",
        "category": cat,
        "zone_id": zone,
        "zone_name": zone_row["zone_name"],
        "cost_lakhs_inr": cost,
        "carbon_reduction_tco2_per_year": carbon,
        "resilience_benefit_raw": resilience,   # 0-100 scale, pre-normalization
        "population_benefited": pop_benefited,
    })

df = pd.DataFrame(rows)
df.to_csv("projects.csv", index=False)
print(f"Wrote projects.csv with {len(df)} rows")
print(df.head(10).to_string())
