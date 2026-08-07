# LLM Council

![llmcouncil](header.jpg)

The idea of this repo is that instead of asking a question to your favorite LLM provider (e.g. OpenAI GPT 5.1, Google Gemini 3.0 Pro, Anthropic Claude Sonnet 4.5, xAI Grok 4, eg.c), you can group them into your "LLM Council". This repo is a simple, local web app that essentially looks like ChatGPT except it uses OpenRouter to send your query to multiple LLMs, it then asks them to review and rank each other's work, and finally a Chairman LLM produces the final response.

In a bit more detail, here is what happens when you submit a query:

1. **Stage 1: First opinions**. The user query is given to all LLMs individually, and the responses are collected. The individual responses are shown in a "tab view", so that the user can inspect them all one by one.
2. **Stage 2: Review**. Each individual LLM is given the responses of the other LLMs. Under the hood, the LLM identities are anonymized so that the LLM can't play favorites when judging their outputs. The LLM is asked to rank them in accuracy and insight.
3. **Stage 3: Final response**. The designated Chairman of the LLM Council takes all of the model's responses and compiles them into a single final answer that is presented to the user.

## Vibe Code Alert

This project was 99% vibe coded as a fun Saturday hack because I wanted to explore and evaluate a number of LLMs side by side in the process of [reading books together with LLMs](https://x.com/karpathy/status/1990577951671509438). It's nice and useful to see multiple responses side by side, and also the cross-opinions of all LLMs on each other's outputs. I'm not going to support it in any way, it's provided here as is for other people's inspiration and I don't intend to improve it. Code is ephemeral now and libraries are over, ask your LLM to change it in whatever way you like.

## Setup

### 1. Install Dependencies

The project uses [uv](https://docs.astral.sh/uv/) for project management.

**Backend:**
```bash
uv sync
```

**Frontend:**
```bash
cd frontend
npm install
cd ..
```

### 2. Configure API Key

Create a `.env` file in the project root:

```bash
OPENROUTER_API_KEY=sk-or-v1-...
```

Get your API key at [openrouter.ai](https://openrouter.ai/). Make sure to purchase the credits you need, or sign up for automatic top up.

### 3. Configure Models (Optional)

Edit `backend/config.py` to customize the council:

```python
COUNCIL_MODELS = [
    "openai/gpt-5.1",
    "google/gemini-3-pro-preview",
    "anthropic/claude-sonnet-4.5",
    "x-ai/grok-4",
]

CHAIRMAN_MODEL = "google/gemini-3-pro-preview"
```

## Running the Application

**Option 1: Use the start script**
```bash
./start.sh
```

**Option 2: Run manually**

Terminal 1 (Backend):
```bash
uv run python -m backend.main
```

Terminal 2 (Frontend):
```bash
cd frontend
npm run dev
```

Then open http://localhost:5173 in your browser.

# Architecture

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

- **Backend:** FastAPI (Python 3.10+), async httpx, OpenRouter API
- **Frontend:** React + Vite, react-markdown for rendering
- **Storage:** JSON files in `data/conversations/`
- **Package Management:** uv for Python, npm for JavaScript
