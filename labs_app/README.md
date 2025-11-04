# GPTLov Labs App

This directory adapts Elastic's [chatbot RAG example](https://github.com/elastic/elasticsearch-labs/tree/main/example-apps/chatbot-rag-app)
to the GPTLov backend. The React frontend keeps the polished streaming experience while the Flask
API delegates retrieval and answer generation to `gptlov.bot.GPTLovBot`.

## Layout

```
labs_app/
├── api/          # Flask entry point and GPTLov streaming adapter
├── frontend/     # React application (Yarn + Vite)
└── README.md     # This file
```

## Prerequisites

* GPTLov installed in your Python virtual environment (`pip install -e .` at the repo root)
* Lovdata archives prepared or accessible as described in the main README
* Node.js 18+ and Yarn for building the frontend

## Usage

1. **Build the frontend**
   ```bash
   cd labs_app/frontend
   yarn install
   REACT_APP_API_HOST=/api yarn build
   ```
   The production assets are written to `frontend/build/` and served by Flask.

2. **Run the Flask API**
   ```bash
   # From the repository root with your virtualenv activated
   export FLASK_APP=labs_app.api.app
   flask run --debug --port 4000
   ```
   The server exposes `GET /health` and `POST /api/chat` (Server-Sent Events stream). On the
   first request the GPTLov vector store is initialised; subsequent responses reuse the same bot
   instance.

3. **Open the web UI**
   Navigate to [http://localhost:4000/](http://localhost:4000/) to use the experimental labs
   interface. Responses stream into the chat area and matched sources appear in the right-hand
   sidebar where each card expands to show text snippets.

### Frontend development server

Instead of building the static assets you can run the React dev server:

```bash
cd labs_app/frontend
REACT_APP_API_HOST=http://localhost:4000/api yarn start
```

This starts the app on port `3000` with hot reloading while the Flask API continues to run on
port `4000`.

## Notes

* The original Elastic example shipped additional Docker/Kubernetes manifests and Elasticsearch
  ingestion scripts. They are intentionally omitted here because GPTLov already handles Lovdata
  ingestion and search backends.
* Source cards fall back to local file paths when a public URL is unavailable; customise
  `labs_app/api/chat.py` if you want to produce deep links into your public document store.
* The UI strings and defaults have been localised for Norwegian law prompts—feel free to tweak
  `labs_app/frontend/src/` to match your branding.
