# FRIS Faculty Demo Setup Guide

## A. Scholarly API setup

OpenAlex is the required source for this prototype and works without an API key. Optional `OPENALEX_EMAIL` identifies a polite-pool contact; use an address approved for that purpose. OpenAlex docs: https://developers.openalex.org/ and API: https://api.openalex.org/.

ORCID lookup is performed by matching the supplied, checksum-validated ORCID against OpenAlex. Direct ORCID public-record enrichment is optional and requires Public API credentials from https://orcid.org/developer-tools; follow https://info.orcid.org/documentation/ to register. Set `ORCID_CLIENT_ID` and `ORCID_CLIENT_SECRET` in the backend environment. Do not put credentials in frontend variables. The current demo lookup does not depend on ORCID credentials.

## B. Local setup

Install Git, Python 3.11+, Node.js 24.15+, and Docker Desktop with Compose. Clone the project, then configure the backend:

```powershell
git clone https://github.com/Prince-Singhalia/FRIS.git
cd FRIS
Copy-Item .env.example .env
```

Set strong local `POSTGRES_PASSWORD` and `SECRET_KEY` values in `.env`. `OPENALEX_EMAIL` and ORCID credentials are optional. Start the existing database/API/Prefect stack with `docker compose up --build`; the API docs are at http://localhost:8000/docs and health at http://localhost:8000/health/live.

Run the web UI separately:

```powershell
cd frontend
npm ci
$env:VITE_API_BASE_URL = 'http://localhost:8000/api/v1'
npm run dev
```

Open http://localhost:5173. Do not use `VITE_` variables for secrets; Vite exposes them in browser code.

## C. Deployment preparation

The app is not deployed by this guide. Create accounts at https://vercel.com/ and https://render.com/ and connect the public GitHub repository.

For Vercel, set Root Directory to `frontend`, framework to Vite, build command `npm run build`, output directory `dist`, and `VITE_API_BASE_URL` to the deployed API base ending in `/api/v1`.

For Render, create a Docker web service from the repository with Docker context `backend` and Dockerfile `backend/Dockerfile`; set start command to `uvicorn app.main:app --host 0.0.0.0 --port $PORT`. Configure PostgreSQL credentials, `SECRET_KEY`, `BACKEND_CORS_ORIGINS` with the exact Vercel origin, and optional provider variables in the Render dashboard. Do not enable demo seeding in production. The current Compose setup assumes PostgreSQL and Prefect for the existing tenant workflow; the public lookup endpoints themselves are stateless. Confirm migration behavior and service health before exposing a deployment. After deploy, use the service URL plus `/docs`; copy the Vercel URL from the Vercel deployment overview.

## D. Faculty demonstration

1. Open the Vercel site, or locally http://localhost:5173.
2. Choose Name and enter a researcher name, or choose ORCID and enter a complete ORCID.
3. Explain that name results are possible matches and require a human to choose the correct person.
4. Select the candidate whose displayed affiliation and identifiers match the researcher.
5. Show retrieved OpenAlex works, year, venue, type, authors, citations, and source links. DOI links open doi.org when present; source links open OpenAlex.
6. Use “Load more publications” to demonstrate page-based pagination (25 records per page; OpenAlex basic paging is limited to 10,000 works).
7. Explain that missing fields are absent in the provider record and not filled with invented values.

## E. Troubleshooting

- Invalid ORCID: check the 16-character ORCID and checksum; remove typos and retry.
- Search cannot connect: confirm API is running at port 8000 and `VITE_API_BASE_URL` includes `/api/v1`.
- Browser CORS error: add the exact frontend origin to `BACKEND_CORS_ORIGINS` and restart the API. Local defaults include ports 5173, 5174, and 3000 on both localhost and 127.0.0.1.
- No matching researcher: try a variant spelling or ORCID; OpenAlex coverage is not exhaustive.
- Empty publications: verify the selected OpenAlex author; some records have no indexed works.
- OpenAlex 429/5xx or timeout: wait and retry; these reflect provider/network limits and the UI reports retrieval errors.
- Docker refuses to start: ensure Docker Desktop is running and required `.env` values are set; inspect `docker compose logs api db`.
- Vercel build cannot find app: verify Root Directory is `frontend` and build output is `dist`.
- CORS/API unavailable after deployment: check Render health and exact Vercel origin configuration.

## F. Action checklist

### Completed in the repository

- Fetched and inspected teammate commit `bc94bae`, then fast-forwarded local `main`.
- Added public OpenAlex author/ORCID/works API routes and the React demonstration interface.
- Added this setup and demonstration guide.

### You need to do

- Install/run Docker and Node locally, set local secrets, and follow the demo steps.
- Create Vercel and Render services and configure their environment variables if you want a public deployment.
- Test searches with the institution’s intended researcher examples and confirm identity before presenting attribution.

### Account authentication required

- Sign in to Vercel and Render and authorize their GitHub integrations; Codex does not have those deployment account credentials.
- Register ORCID Public API credentials only if direct ORCID record enrichment is needed.

### Deferred until after the demonstration

- Production deployment and live-site testing; direct ORCID enrichment; automated scheduled discovery; large-scale synchronization; advanced identity resolution and deduplication; review workflow; Prefect orchestration for this public search UI; Redis, Kafka, Kubernetes, and expanded CI/CD.
