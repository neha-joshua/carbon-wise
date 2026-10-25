# Gated migration from GCC zones to wards

The current model is a 15-zone model. `wards.csv` is misleadingly named: each of its 15 rows is keyed by `zone_id`. Do not treat these as ward records and do not allocate a project to a ward based on a zone label.

Ward-level migration is blocked until all of the following are obtained and validated:

1. An authoritative GCC ward/division boundary layer with publication/version date, coordinate reference system, and stable ward IDs.
2. Population counts by the same ward IDs with a known reference year and documented method.
3. Vulnerability observations at that same geography or a defensible source geography and method for deriving ward scores.
4. A verified project-location crosswalk to the same boundaries; no unsupported centroid or name matching.
5. Documentation of boundary changes, missing wards, one-to-many project coverage, and any spatial allocation assumptions.
6. Tests for identifier uniqueness, complete coverage, CRS compatibility, and no silent many-to-many joins.

Until those checks pass, maintain the 15-zone model, clearly label the geography as zones, and keep unlocated or ambiguous real projects out of location-dependent scoring.
