# InGame Studio

**An AI insights engine for live football: it reads match tracking data as it happens, explains why each moment matters, and tells that story differently for every viewer, in English and Spanish.**

**Live demo (no sign-in needed): https://app-ingame-kkubzmbwg2t4c.greensand-a835732b.eastus.azurecontainerapps.io/**

Built for the Microsoft "Inside the Game" hackathon. **Platform:** web application for desktop browsers (Chrome or Edge), Python 3.12 backend, React 18 frontend; runs locally, in Docker, or on Azure Container Apps.

> **Data notice:** every club, player, match and number in this project is synthetic. The two clubs (Northbridge Lions and Harbourside City) and all players are fictional. Nothing here is an official feed or refers to a real person or organisation.

## Try it

1. Open the live demo: https://app-ingame-kkubzmbwg2t4c.greensand-a835732b.eastus.azurecontainerapps.io/
2. Your match starts from kick-off as soon as the page opens, and it is **yours alone**: every browser tab gets its own match, so Play, Pause, Reset and the speed buttons (2x, 5x, 10x, 20x) never affect anyone else. Reloading the page continues your match. It lasts 94:30; pressing Play after full time restarts it.
3. Pick a persona in the top bar (Casual, Tactical, Club, Fantasy) and a language (EN or ES): every tab follows it.
4. Open the **Tactics** tab for replays of the key moments, **Players** for heatmaps, passing lanes and radar, **Recap** for the highlights video, and use the chat bubble (bottom right of the match tab) to ask the Match Analyst about the match as it stands.
5. `/api/llm/status` on the same address shows the live status: Microsoft Foundry connected, the Cosmos DB store and the Agent Framework workflow.

The app is deployed from this repository by GitHub Actions to Azure Container Apps on every push to `main`.

## Pitch

**What we built.** A complete match-intelligence studio. A seeded simulator plays a 94-minute match (22 players and a ball at 25 Hz, with passes, shots, goals, tackles, pressure, turnovers, fouls, cards and substitutions, and the teams changing ends at half-time). Every event is turned into structured facts, explained by a language model, checked against the tracking data, and rendered as ticker lines, telestrator vectors, alerts, player cards, replay clips, a highlights video and a match story.

**Which Microsoft and Azure technologies it uses.**

| Technology | How it is used |
|---|---|
| **Microsoft Foundry (Azure AI Foundry)**, `gpt-4.1-mini` deployment | Writes every event narrative, the match stories and the tactical analyses, in English and Spanish. Calls go through one adapter with retry and back-off, a rolling token budget that stays under the 150k tokens-per-minute quota, and a verified, single-flight, never-cache-a-failure cache. `GET /api/llm/status` and the on-screen badge (`AZURE FOUNDRY - CACHED / LIVE`) show where each text came from. |
| **Microsoft Agent Framework** (`agent-framework-core`, `agent-framework-openai`) | The four pipeline agents are Agent Framework executors in one workflow graph (`backend/agents/af_workflow.py`): Tactician, Pundit, Verifier, Director, with the Verifier-to-Pundit retry loop as a graph edge and the hand-offs recorded in each insight's `agent_trace`. A fifth agent, the **Match Analyst** (`backend/agents/analyst_agent.py`), is an Agent Framework `Agent` on the Foundry model that answers viewer questions by calling tools. |
| **Azure Cosmos DB for NoSQL** (serverless) | The shared, durable narrative store (`backend/cosmos_store.py`): every verified answer is written through to Cosmos DB and a fresh or restarted instance loads them all at start-up. If Cosmos DB is down the app keeps working from memory and the bundled file. |
| **Azure Container Apps + Azure Container Registry + Log Analytics** | Hosting target. `infra/main.bicep` provisions them, `Dockerfile` builds one image (React build served by FastAPI), `.github/workflows/deploy-azure.yml` builds, pushes and updates the app. The Foundry key is passed as a Container Apps secret. |
| **Model Context Protocol (MCP)** | `backend/mcp_server.py` is our own MCP server that exposes 7 match-analytics tools (telemetry, pass difficulty, control-vs-chaos index, player metrics, match overview, recap, narrative grounding check). The Match Analyst agent calls these tools itself to answer questions about the live match, and `.vscode/mcp.json` registers the server so it can also be called from VS Code agent mode. |
| **GitHub** | Source, Actions workflow for tests, the frontend build and deployment. |

What is **not** used: Microsoft Fabric, Azure's own MCP server and Azure Functions. We list only what is wired in. The Agent Framework graph can be switched off with `INGAME_ORCHESTRATION=plain` (the same four steps then run as a plain loop, which is what the tests compare against).

**What it does.**

- **Ingest and interpret:** events and tracking frames stream over a WebSocket (`/ws/match-stream`); more can be posted to `/api/ingest`. A math engine turns them into possession, pass accuracy, expected threat, territory, field tilt, a control-vs-chaos index, heatmaps, passing lanes, a six-axis player radar and player ratings.
- **Explain why a moment matters:** a Tactician agent extracts a fact pack, a Pundit agent asks Foundry for a narrative, a Verifier agent checks every name and number against the telemetry (and rejects and retries up to twice), and a Director agent adapts the verified text into four audience personas and two languages. The four run as a Microsoft Agent Framework workflow. Match stories and tactical notes get the same check-and-retry treatment.
- **Ask the Match Analyst:** a chat bubble in the bottom-right corner of the match tab. An Agent Framework agent answers by calling the MCP tools, which read the match as it stands at the current clock (it cannot know or hint at what has not happened yet). The answer follows the persona chosen in the top bar, and the Club persona answers as a fan of the chosen club. It is checked against the tool results before it is shown, together with the tools it used (`POST /api/analyst/ask`).
- **Personalise:** one persona switcher applies to every tab: Casual fan, Tactical purist, Club loyalist (pick a club) and Fantasy scout. A viewer can also pick a language, follow a player, or spotlight a single metric.
- **Replay and recap:** the Tactics tab replays the six key moments (10 seconds before and after) with the tactical shape drawn on the pitch. The Recap tab plays a highlights video made from the same clips, plus the match story and turning points.
- **Developer surface:** REST and WebSocket APIs, an overlay message format (below) and the MCP tools.

**What problem it solves.** Broadcasters and streaming apps cannot put a human analyst next to every viewer. Fans who want the "why" of a moment, in their language and at their level, get a generic commentary line instead. InGame Studio shows how a grounded language model can produce accurate, personalised and multilingual explanations for every moment of a match, in real time, without inventing facts. Broadcasters, streaming and fantasy apps, and developers (through the MCP tools and APIs) are the intended users.

**What is new.** The verification loop. The model writes; a deterministic verifier compares every player name and number to the tracking data; a rejected draft goes back with a critique; a draft that still fails is never stored and the viewer sees a template instead. Together with the cache and the token budget, this makes model output safe to put in front of viewers and cheap enough to serve to many.

**Built during the hackathon period** (from 22 October 2026).

## Architecture

```mermaid
flowchart LR
    SIM["Seeded match simulator<br/>22 players + ball, 25 Hz"] -->|frames and events| API
    EXT["External events<br/>POST /api/ingest"] --> API
    subgraph API["FastAPI backend"]
        MATH["Math engine<br/>xT, territory, chaos, radar"]
        TAC["Tactician<br/>fact pack"] --> PUN["Pundit<br/>asks the model"]
        AGENTS["Microsoft Agent Framework workflow<br/>Tactician, Pundit, Verifier, Director"] -.- TAC
        ANALYST["Match Analyst agent<br/>Agent Framework + MCP tools"]
        PUN --> VER["Verifier<br/>checks names and numbers"]
        VER -->|reject + critique, max 2 retries| PUN
        VER --> DIR["Director<br/>personas, languages, overlays"]
        CACHE[("Narrative cache<br/>single flight, never caches failures")]
        CACHE <--> COSMOS[("Azure Cosmos DB<br/>shared narrative store")]
        BUDGET["Token budget<br/>60% of 150k TPM"]
    end
    PUN <--> CACHE
    PUN --> BUDGET --> FOUNDRY["Microsoft Foundry<br/>gpt-4.1-mini"]
    MATH --> TAC
    DIR -->|WebSocket + REST| UI["React dashboard<br/>pitch, tactics replay, recap video"]
    API --- MCP["MCP server<br/>7 analytics tools"]
    ANALYST --> MCP
    ANALYST --> FOUNDRY
```

## Overlay message format

Everything the UI renders arrives as JSON over `/ws/match-stream`, so another renderer can consume it:

```json
{ "type": "insight", "timestamp": "2026-10-27T10:12:44Z", "data": { "...VerifiedInsight..." } }
```

`type` is one of `telemetry`, `event`, `insight`, `metric_alert`, `control`, `pong`. A `VerifiedInsight` carries, besides the text for every persona and language, the timing a graphics engine needs to place it on the live feed: `frame_index` and `match_clock` (when the moment happened), `period`, `display_from_frame` and `display_until_frame` (25 Hz tracking frames) and `display_duration_sec`, plus `lower_third_ticker`, `telestrator_vectors` (arrows, zones and lines in pitch metres), `metrics`, `grounding_score` and `narrative_source`. The full definitions are in `data/schema.json`.

## What is implemented

- A Python FastAPI service with REST endpoints and a WebSocket match stream. **Each viewer has their own match** (their own clock, play state, score and analytics, plus their own analyst context), identified by a random session id the browser keeps in `sessionStorage` and sends as the `X-Session-Id` header and `?session=` on the WebSocket (`backend/sessions.py`). The model's cached answers, the replay clips and the data files are shared, because every match plays the same seed. A request without an id uses one default shared match, which is where external event feeds (`/api/ingest`) land. The match ends at 94:30 and pressing Play afterwards restarts it.
- A seeded simulator. Events are emitted at the frame where each action happens, from the same state as the tracking data. Event types: `pass`, `shot`, `goal`, `tackle` (won and lost), `turnover`, `pressure`, `foul`, `card`, `substitution`. **Possession changes** are the events with `tactical_metrics.possession_change = true` (interceptions are `turnover`, won tackles are `tackle`). Teams change ends at half-time; substitutes and sent-off players join and leave the pitch.
- Analytics: possession, pass accuracy and difficulty, speed and distance thresholds, expected threat, territory, field tilt, control vs chaos, heatmaps, passing lanes, shot map, a percentile-ranked six-axis radar and player ratings.
- Real-time intelligence: player name tags, sprint and ball-speed alerts, distance and pass-count milestones.
- Tactics tab: the six key moments (the same moments as the recap turning points) with replay clips cut from the tracking data.
- Recap tab: highlights video from the clips, match story and turning points, in English and Spanish.
- Personas, club and player focus, single-metric spotlight, English and Spanish.
- Per-event Spanish persona text comes from templates; match stories, tactical notes and the per-event narratives are model-written in both languages. The UI labels are English.
- Limits we state openly: goalkeeper-save, penalty, offside, corner and injury events are not simulated; metrics come from tracking data, not from a video model (video-based auto-eventing is the production path, not part of this build).

## Foundry usage, the cache and cost control

Model answers for a given match moment never change, so each one is generated once and reused (`backend/narrative_cache.py`):

- **Cache key** covers the facts, the model deployment and a prompt version, so a changed prompt or model never serves stale text.
- **Single flight:** many viewers asking for the same new moment cause one model call.
- **Never caches failures:** text that fails verification, or a model error, is not stored.
- **The live stream never waits for the model:** a miss shows the local template immediately and warms the cache in the background.
- **Token budget:** a rolling window keeps usage at 60% of the 150k tokens-per-minute quota.
- **Shared store:** with `COSMOS_ENDPOINT` and `COSMOS_KEY` set, every verified answer is also written to Azure Cosmos DB, and a new instance loads them all at start-up. `python scripts/sync_cache_to_cosmos.py` uploads the pre-generated cache once.
- **Pre-generation:** `python scripts/pregenerate_narratives.py` writes every event narrative, the match stories and the tactical analyses (English and Spanish) into `data/narrative_cache.json`, so the default demo match is served with no model calls. `python scripts/prune_cache.py --apply` removes entries that do not belong to the current match.

Without credentials (or with `INGAME_LLM=off`) everything runs on the local deterministic engine.

## Run it

Requirements: Python 3.12, Node.js 20, and the packages in `requirements.txt`. To use Azure AI Foundry, copy `.env.example` to `.env` and fill in the endpoint, key and deployment name (never commit `.env`).

**Option 1: Docker (one command to build, one to run).**

```bash
docker build -t ingame-studio .
docker run -p 8000:8000 --env-file .env ingame-studio
```

Open http://localhost:8000. Leave out `--env-file .env` to run on the bundled narrative cache and the local engine.

**Option 2: from source.**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn backend.main:app --reload
```

In a second terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Open the URL printed by Vite.

## Deploy to Azure Container Apps

`infra/main.bicep` creates the registry, a Log Analytics workspace, the Container Apps environment and one container app (1 CPU, 2 GB, one replica, because each viewer's match lives in that instance's memory; scaling out needs sticky sessions). The workflow `.github/workflows/deploy-azure.yml` deploys it after the tests pass. Add these repository secrets: `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`, `AZURE_RESOURCE_GROUP`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `COSMOS_ENDPOINT`, `COSMOS_KEY`. Without them the deploy job skips itself. The Bicep has been written to the current schemas but has not been run against a subscription from this repository yet.

## Use the MCP tools

`.vscode/mcp.json` registers the server for VS Code agent mode. To run it by hand: `python -m backend.mcp_server` (stdio JSON-RPC).

## Useful API routes

Health and status, controls, alerts, insights, recap, event and telemetry ingestion, event listing, analytics and the `/ws/match-stream` WebSocket. See `backend/app.py`. The Recap, Tactics and story endpoints are `GET /api/recap`, `/api/tactical?language=`, `/api/story?persona=&language=&club=` and `/api/llm/status`. Replay clips are served by `GET /api/clips/{event_id}` from `data/match_clips.json`.

## Synthetic match data

A fixed seed (default 2036: Northbridge Lions 3, Harbourside City 1, with a second-yellow red card for Harbourside City) makes the match repeatable; set `SIMULATION_SEED` to get another. `data/synthetic_events.json` is the generated event export for the default seed, `data/synthetic_match_snapshot.json` the final frame and analytics, `data/synthetic_match_metadata.json` the provenance record. Regenerate with:

```powershell
python scripts/generate_90min_dataset.py --seed 2036
python scripts/generate_clips.py
python scripts/pregenerate_narratives.py
```

The simulator uses simplified decision and movement rules; it is not a physics reconstruction of professional play.

## Verification

`python run_all_tests.py` runs the backend suite offline (`tests/conftest.py` sets `INGAME_LLM=off`, so no test calls Azure). Last run: 415 passed. `cd frontend; npm run build` builds with zero TypeScript errors.

## Security

- **Secrets:** the Foundry and Cosmos DB keys are read from environment variables (a git-ignored `.env` locally, Container Apps secrets in Azure). They are never logged, returned by an endpoint or stored in the image; a test scans the repository for key-like strings.
- **Writing events:** set `INGAME_API_KEY` and `POST /api/ingest` and `/api/events` then require a matching `X-API-Key` header (batches are capped at 500 events). Unset, they stay open for local development.
- **Cost control:** the Match Analyst is limited to 12 questions a minute per client and 90 in total, questions are capped at 400 characters, and all model calls share the 150k tokens-per-minute budget.
- **Browser access:** CORS allows only the local dev server (or the origins in `INGAME_CORS_ORIGINS`, never a wildcard); responses carry `nosniff`, `X-Frame-Options` and a referrer policy; WebSocket clients and message sizes are capped.
- **Per-viewer matches:** playback control only affects the caller's own match. Sessions are capped at 40, idle ones are removed after 15 minutes, and a viewer's match pauses when their browser disconnects.
- **Known limits:** there is no sign-in. One CPU core runs roughly 100 viewer-times-playback-speed units of simulation (measured: 30 viewers at normal speed, 20 at 5x or 10 at 10x); beyond that the matches slow down rather than fail. Sessions live in the memory of one instance, so scaling out needs more replicas together with sticky sessions. The model's text is verified against the data but a user question can still try to steer the analyst's wording (it has read-only tools and its numbers are checked).
- Report vulnerabilities as described in [SECURITY.md](SECURITY.md).

## Licence and conduct

Released under the [MIT Licence](LICENSE). This project follows the [Microsoft Open Source Code of Conduct](CODE_OF_CONDUCT.md). Main open-source dependencies: FastAPI, Uvicorn, Pydantic, NumPy, React, Vite, TypeScript (all permissively licensed).
