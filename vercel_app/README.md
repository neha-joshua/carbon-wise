# CarbonWise — Vercel web edition

A static browser-side prototype intended to deploy from this folder as the Vercel project root. It is separate from the existing Streamlit dashboard under `dashboard/`.

## Deploy from GitHub

1. Push this folder to the `main` branch of `neha-joshua/carbon-wise`.
2. In Vercel, choose **Add New → Project** and import `neha-joshua/carbon-wise`.
3. Set **Root Directory** to `vercel_app` and **Framework Preset** to **Other**. Leave build and output commands blank; this is a static site.
4. Deploy. Vercel will assign a `*.vercel.app` URL. Check deployment visibility in Vercel project settings.

No environment variables or API keys are required. CSV parsing, portfolio ranking and photo pixel counting happen in the visitor's browser; the uploaded files are not sent to an application backend.

## Current prototype boundaries

The planner uses a weighted, dataset-relative project score followed by greedy budget fitting. It compares that shortlist with lowest-cost and carbon-per-cost greedy baselines. It does not run the Streamlit app's NSGA-II optimizer, guarantee a globally optimal portfolio, persist uploads/audits, verify source claims, or establish causal impact. The example rows are synthetic. The photo feature counts pixels matching a simple green color threshold; it does not detect trees, vegetation cover, flooding or infrastructure objects.
