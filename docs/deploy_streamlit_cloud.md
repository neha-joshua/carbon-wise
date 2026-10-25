# Put CarbonWise on a shareable web link

## Recommended host

CarbonWise is a Streamlit app. **Streamlit Community Cloud** is the shortest path to a shareable `*.streamlit.app` URL: it deploys from a GitHub repository and supports public or private repositories. Vercel Functions do not support acting as a WebSocket server, while Streamlit uses a persistent interactive connection; Vercel is therefore the wrong direct host for this app. Keep Vercel in mind only if the interface is rebuilt as a conventional frontend/backend web app.

## Before publishing

The repository contains the supplied project CSV, derived data, and tender register. The official GCC report PDF remains in the local project and is linked from the app's evidence page and documentation; it is not stored in the GitHub repository. A public GitHub repository makes the committed files visible to anyone. Choose a private repository if you do not want the source files public; Streamlit Community Cloud can deploy from private repositories, but viewer access will depend on the app's sharing settings and login. The optional OpenAI explanation does not need a key; the deployed app works without one and uses its local rule-based fallback.

## One-time setup

1. Make a GitHub repository for this project. Use **private** unless you want all included code/data/source files to be publicly downloadable.
2. Upload the contents of this `carbonwise` folder to the repository root (not the enclosing `outputs` directory). Keep `requirements.txt`, `dashboard/`, `src/`, and `data/` at that root level.
3. Open [Streamlit Community Cloud](https://share.streamlit.io/) and sign in with GitHub.
4. Choose **Create app**, select the repository and branch, set **Main file path** to `dashboard/app.py`, select Python **3.12**, and deploy.
5. Once the health check succeeds, use the Streamlit URL as the shareable website address. Test both workspaces there. The Scenario Lab remains synthetic and should be presented as a demonstration.

Official deployment instructions: [Deploy your app on Community Cloud](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy).

## Updates

Changes pushed to the selected repository branch are automatically redeployed. Do not add `.env` or an API key to GitHub. No secret is required for the current default app flow.

## Local run

From this project folder:

```bash
python3 -m pip install -r requirements.txt
python3 -m streamlit run dashboard/app.py
```

The dashboard now resolves its zone data relative to the project root, so the app entrypoint can be launched from the repository root on a hosted service as well as locally.
