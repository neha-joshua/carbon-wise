# Deploy CarbonWise on Streamlit Community Cloud

CarbonWise is a Streamlit app and uses Streamlit's persistent interactive connection. The repository root contains `requirements.txt`, and the entry point is `dashboard/app.py`. Community Cloud runs the application from the repository root, so launch with the repository-relative entry point.

## Current deployment readiness

- Entrypoint: `dashboard/app.py`.
- Required data and UI assets are in the repository (`data/`, `src/`, `dashboard/`). The excluded GCC report PDF is linked externally by the evidence workspace and is not needed at startup.
- `requirements.txt` includes the NSGA-II package, Streamlit, Plotly, pandas/numpy, Pillow for local photo analysis, and openpyxl for Excel uploads.
- Uploaded CSV/Excel and photo contents are handled in the Streamlit session; they are not written into the Git repository by the app.
- The optional LLM explanation continues to use a rule-based fallback; the app does not require an API key.
- No `.env`, app secrets, or user uploads should be committed.

## Deploy steps

1. Ensure the CarbonWise repository contains the latest working commit on the branch to deploy.
2. Open [Streamlit Community Cloud](https://share.streamlit.io/) and sign in with GitHub.
3. Select **Create app**, then choose repository `neha-joshua/carbon-wise`, branch `main`, and main file path `dashboard/app.py`.
4. In **Advanced settings**, select Python 3.12 (the Community Cloud default in the current documentation) and deploy.
5. Wait for the install/startup health check. Open the generated `*.streamlit.app` URL and check the Evidence Room, the Scenario Lab, and the five Live Studio tabs. Test uploads with non-confidential sample data.
6. In the app settings, set public/private sharing as intended. Community Cloud's sharing settings control viewer access.

A successful GitHub commit alone does not mean the Streamlit app is deployed. Do not claim a public URL until the cloud health check finishes and the URL opens in a separate browser session.

## Local run

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run dashboard/app.py
```

Then open the `Local URL` Streamlit prints (usually `http://localhost:8501`). In Live Studio, click **Load synthetic demo**, confirm the detected fields under **Upload & prepare**, then open **Compare plans** and select **Generate investment plan**. The app labels those example rows as invented practice data.
