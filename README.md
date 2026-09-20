# LLM Council

![LLM Council](header.jpg)

Ask not one LLM, but a **council of LLMs**. LLM Council is a local ChatGPT-style web app that sends your query to multiple models via [OpenRouter](https://openrouter.ai/), has them anonymously review and rank each other's answers, and then has a Chairman model synthesize a single final response.

## How It Works

Every user message runs through a 3-stage deliberation pipeline:

1. **Stage 1 — First Opinions**
   The full conversation history is sent to every council model in parallel (`asyncio.gather`). Individual responses are shown in a tab view so you can inspect each model side by side.

2. **Stage 2 — Anonymous Peer Review**
   Responses are anonymized as `Response A, B, C…` so models can't play favorites. Each council model evaluates every response and returns a `FINAL RANKING:` list. The backend parses these rankings, de-anonymizes them via a `label_to_model` map, and computes **aggregate rankings** (average rank position, sorted best → worst). Raw evaluation text plus the extracted ranking are both shown in the UI for transparency.

3. **Stage 3 — Chairman Synthesis**
   The designated Chairman model receives the conversation history, all Stage 1 responses, all Stage 2 rankings, and the memory summary, then produces the final comprehensive answer.

```
User Query
  ↓
Stage 1: parallel queries → [individual responses]
  ↓
Stage 2: anonymize → parallel ranking queries → [evaluations + parsed rankings]
  ↓
Aggregate rankings (avg position)
  ↓
Stage 3: Chairman synthesis
  ↓
{ stage1, stage2, stage3, metadata }
```

## Features

- **Multi-model deliberation** — configurable council + chairman via `backend/config.py`
- **Anonymized peer review** — prevents bias during ranking; de-anonymized client-side for display only
- **Aggregate rankings** — average position across all peer evaluations
- **Conversation memory** — per-conversation short-term buffer (last 20 exchanges) + concise summary injected into Stage 2/3 prompts
  - `local` mode (default): fast on-device heuristic summarizer
  - `model` mode: LLM-based summarization via Chairman model
  - Switchable at runtime via `GET/POST /api/memory/mode`, clearable per conversation
- **Streaming (SSE)** — `POST /api/conversations/{id}/message/stream` streams `stage1_start → stage1_complete → stage2_start → … → complete` events
- **Persistent conversations** — JSON files in `data/conversations/`, auto-generated titles, full history passed as context on every turn
- **Transparent UI** — tabs for every raw model output, parsed rankings shown for validation, markdown rendering throughout
- **Graceful degradation** — failed models return `None` and are skipped; the council continues with successful responses

## Tech Stack

| Layer    | Technology |
|----------|------------|
| Backend  | FastAPI, Uvicorn, `httpx` (async), Pydantic, OpenRouter API |
| Frontend | React 19 + Vite, `react-markdown` |
| Storage  | JSON files in `data/conversations/` |
| Python mgmt | [uv](https://docs.astral.sh/uv/) (Python ≥ 3.10), npm for JS |

## Project Structure

```
llm-council/
├── backend/
│   ├── main.py        # FastAPI app, REST + SSE endpoints (port 8001)
│   ├── council.py     # Stage 1/2/3 orchestration, ranking parse + aggregation
│   ├── openrouter.py  # query_model / query_models_parallel client
│   ├── memory.py      # short-term buffer + local/model summarization
│   ├── storage.py     # JSON conversation persistence
│   └── config.py      # COUNCIL_MODELS, CHAIRMAN_MODEL, keys, memory settings
├── frontend/src/
│   ├── App.jsx            # orchestration, conversations + metadata state
│   ├── api.js             # backend API client
│   └── components/
│       ├── ChatInterface.jsx  # multiline input (Enter send / Shift+Enter newline)
│       ├── Stage1.jsx         # tab view of individual responses
│       ├── Stage2.jsx         # raw evaluations + extracted + aggregate rankings
│       └── Stage3.jsx         # final chairman answer
├── data/conversations/    # persisted chats (gitignored)
├── scripts/               # helper scripts
├── start.sh               # run backend + frontend together
└── pyproject.toml         # Python deps (uv)
```

## Prerequisites

- Python 3.10+ with [uv](https://docs.astral.sh/uv/) installed
- Node.js 18+ with npm
- An [OpenRouter API key](https://openrouter.ai/) with credits

## Setup

### 1. Install dependencies

Backend (from repo root):

```bash
uv sync
```

Frontend:

```bash
cd frontend
npm install
cd ..
```

### 2. Configure API key

Create a `.env` file in the project root:

```bash
OPENROUTER_API_KEY=sk-or-v1-...
```

Optional memory tuning (defaults shown):

```bash
MEMORY_MODE=local
MEMORY_LOCAL_MAX_SENTENCES=3
```

### 3. Configure models (optional)

Edit `backend/config.py`:

```python
COUNCIL_MODELS = [
    "mistralai/devstral-2512:free",
    "xiaomi/mimo-v2-flash:free",
    "kwaipilot/kat-coder-pro:free",
    "tngtech/deepseek-r1t2-chimera:free",
    "nvidia/nemotron-3-nano-30b-a3b:free",
    "deepseek/deepseek-r1-0528:free",
    "meta-llama/llama-3.3-70b-instruct:free",
]

CHAIRMAN_MODEL = "openai/gpt-oss-120b:free"
```

Any [OpenRouter model ID](https://openrouter.ai/models) works. The chairman may be a council member or a different model. Use `scripts/` helpers (e.g. connectivity tests) to verify a model ID before adding it.

## Running the Application

Option 1 — start script (backend + frontend):

```bash
./start.sh
```

Option 2 — run manually:

Terminal 1 (backend):

```bash
uv run python -m backend.main
```

Terminal 2 (frontend):

```bash
cd frontend
npm run dev
```

Then open **http://localhost:5173** (backend health: **http://localhost:8001/**).

> Ports: backend `8001`, frontend `5173` (Vite default). If you change them, update CORS origins in `backend/main.py` and the API base URL in `frontend/src/api.js`.

## Architecture

```mermaid
flowchart TD

subgraph group_frontend["React client"]
  node_app_boot["React bootstrap<br/>Vite entry<br/>[main.jsx]"]
  node_app_shell["Application shell<br/>React composition<br/>[App.jsx]"]
  node_api_client["Backend API client<br/>HTTP client<br/>[api.js]"]
  node_chat["Prompt chat<br/>React component<br/>[ChatInterface.jsx]"]
  node_stages["Council stage views<br/>React components<br/>[Stage1.jsx]"]
  node_sidebar["Conversation sidebar<br/>React component<br/>[Sidebar.jsx]"]
end

subgraph group_backend["FastAPI backend"]
  node_api{{"FastAPI application<br/>HTTP API<br/>[main.py]"}}
  node_memory["Session memory<br/>conversation state<br/>[memory.py]"]
  node_storage["Conversation storage<br/>JSON persistence<br/>[storage.py]"]
  node_model_policy["Council model policy<br/>runtime configuration<br/>[config.py]"]
  node_openrouter_adapter["OpenRouter adapter<br/>LLM provider adapter<br/>[openrouter.py]"]
end

subgraph group_pipeline["Council pipeline"]
  node_workflow{{"Council coordinator<br/>workflow orchestration<br/>[council.py]"}}
  node_first_opinions["First opinions<br/>pipeline stage<br/>[council.py]"]
  node_peer_review["Anonymous peer review<br/>pipeline stage<br/>[council.py]"]
  node_synthesis["Chairman synthesis<br/>pipeline stage<br/>[council.py]"]
end

subgraph group_external["External and local services"]
  node_json_files[("Conversation JSON files<br/>local filesystem")]
  node_openrouter{{"OpenRouter API<br/>external LLM gateway"}}
  node_api_key["OPENROUTER_API_KEY<br/>environment configuration"]
end

node_dev_start["Local dev launcher<br/>shell launcher<br/>[start.sh]"]

node_dev_start -->|"starts"| node_app_boot
node_dev_start -->|"starts"| node_api
node_app_boot -->|"mounts"| node_app_shell
node_app_shell -->|"composes"| node_chat
node_app_shell -->|"composes"| node_stages
node_app_shell -->|"composes"| node_sidebar
node_chat -->|"submits prompt"| node_api_client
node_sidebar -->|"selects conversation"| node_api_client
node_api_client -->|"HTTP requests"| node_api
node_api -->|"runs deliberation"| node_workflow
node_api -->|"manages sessions"| node_memory
node_memory -->|"persists conversations"| node_storage
node_storage -->|"reads and writes"| node_json_files
node_workflow -->|"stage 1"| node_first_opinions
node_first_opinions -->|"opinions"| node_peer_review
node_peer_review -->|"reviews"| node_synthesis
node_workflow -->|"uses configured models"| node_model_policy
node_first_opinions -->|"completion requests"| node_openrouter_adapter
node_peer_review -->|"completion requests"| node_openrouter_adapter
node_synthesis -->|"completion request"| node_openrouter_adapter
node_openrouter_adapter -->|"async API calls"| node_openrouter
node_api_key -.->|"authenticates"| node_openrouter_adapter

click node_dev_start "https://github.com/meetmendapara09/llm-council/blob/main/start.sh"
click node_app_boot "https://github.com/meetmendapara09/llm-council/blob/main/frontend/src/main.jsx"
click node_app_shell "https://github.com/meetmendapara09/llm-council/blob/main/frontend/src/App.jsx"
click node_api_client "https://github.com/meetmendapara09/llm-council/blob/main/frontend/src/api.js"
click node_chat "https://github.com/meetmendapara09/llm-council/blob/main/frontend/src/components/ChatInterface.jsx"
click node_stages "https://github.com/meetmendapara09/llm-council/blob/main/frontend/src/components/Stage1.jsx"
click node_sidebar "https://github.com/meetmendapara09/llm-council/blob/main/frontend/src/components/Sidebar.jsx"
click node_api "https://github.com/meetmendapara09/llm-council/blob/main/backend/main.py"
click node_memory "https://github.com/meetmendapara09/llm-council/blob/main/backend/memory.py"
click node_storage "https://github.com/meetmendapara09/llm-council/blob/main/backend/storage.py"
click node_workflow "https://github.com/meetmendapara09/llm-council/blob/main/backend/council.py"
click node_first_opinions "https://github.com/meetmendapara09/llm-council/blob/main/backend/council.py"
click node_peer_review "https://github.com/meetmendapara09/llm-council/blob/main/backend/council.py"
click node_synthesis "https://github.com/meetmendapara09/llm-council/blob/main/backend/council.py"
click node_model_policy "https://github.com/meetmendapara09/llm-council/blob/main/backend/config.py"
click node_openrouter_adapter "https://github.com/meetmendapara09/llm-council/blob/main/backend/openrouter.py"

classDef toneNeutral fill:#f8fafc,stroke:#334155,stroke-width:1.5px,color:#0f172a
classDef toneBlue fill:#dbeafe,stroke:#2563eb,stroke-width:1.5px,color:#172554
classDef toneAmber fill:#fef3c7,stroke:#d97706,stroke-width:1.5px,color:#78350f
classDef toneMint fill:#dcfce7,stroke:#16a34a,stroke-width:1.5px,color:#14532d
classDef toneRose fill:#ffe4e6,stroke:#e11d48,stroke-width:1.5px,color:#881337
classDef toneIndigo fill:#e0e7ff,stroke:#4f46e5,stroke-width:1.5px,color:#312e81
classDef toneTeal fill:#ccfbf1,stroke:#0f766e,stroke-width:1.5px,color:#134e4a
class node_app_boot,node_app_shell,node_api_client,node_chat,node_stages,node_sidebar toneBlue
class node_api,node_memory,node_storage,node_model_policy,node_openrouter_adapter toneAmber
class node_workflow,node_first_opinions,node_peer_review,node_synthesis toneMint
class node_json_files,node_openrouter,node_api_key toneRose
class node_dev_start toneNeutral
```
## Tech Stack

## API Reference

Base URL: `http://localhost:8001`

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET`  | `/` | Health check |
| `GET`  | `/api/conversations` | List conversations (metadata) |
| `POST` | `/api/conversations` | Create conversation |
| `GET`  | `/api/conversations/{id}` | Get full conversation |
| `POST` | `/api/conversations/{id}/message` | Run full 3-stage council (blocking) |
| `POST` | `/api/conversations/{id}/message/stream` | Run council with SSE progress events |
| `GET`  | `/api/conversations/{id}/memory` | Get memory (`short` + `summary`) |
| `POST` | `/api/conversations/{id}/memory/clear` | Clear conversation memory |
| `GET`  | `/api/memory/mode` | Get runtime memory mode |
| `POST` | `/api/memory/mode` | Set mode: `{"mode": "local" \| "model"}` |

`POST .../message` returns `{ stage1, stage2, stage3, metadata }`, where `metadata = { label_to_model, aggregate_rankings }`.

## Notes & Gotchas

- Run the backend as `python -m backend.main` **from the repo root** — backend modules use relative imports.
- Ranking parse fallback: if a model ignores the `FINAL RANKING:` format, the parser falls back to extracting `Response X` patterns in order.
- Memory metadata is ephemeral in API responses; conversation JSON persists `memory.short` / `memory.summary` per chat.
- If all council models fail, Stage 3 returns an error message instead of crashing.
