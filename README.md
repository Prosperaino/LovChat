# GPTLov

GPTLov is a lightweight retrieval-augmented chatbot for exploring the Lovdata public law datasets.
It builds a TF-IDF search index over the published HTML/XML documents and can optionally call the
OpenAI API to generate summarised answers from the retrieved context.

## Project structure

```
GPTLov/
├── gptlov/            # Source package
│   ├── bot.py          # Retrieval + generation logic
│   ├── cli.py          # Command-line interface (`gptlov`)
│   ├── ingest.py       # Archive extraction and chunking helpers
│   ├── index.py        # Vector store construction utilities
│   └── settings.py     # Simple configuration / environment handling
├── pyproject.toml      # Project metadata and dependencies
├── README.md           # This file
└── (data/)             # Place archives and generated index here (ignored by git)
```

## Prerequisites

- Python 3.11 or newer (tested with 3.12)
- The Lovdata public archives (e.g. `gjeldende-lover.tar.bz2`, `gjeldende-sentrale-forskrifter.tar.bz2`).
  Copy the files into `data/raw/` inside this repository.
- An OpenAI API key if you want model-generated answers (set the environment variable `OPENAI_API_KEY`).
  Without a key, GPTLov will fall back to returning the best matching excerpts.

Optional environment variables:

| Variable | Purpose |
| --- | --- |
| `GPTLOV_RAW_DATA_DIR` | Custom location of the downloaded archives (`data/raw` by default). |
| `GPTLOV_WORKSPACE_DIR` | Directory to hold extracted files and the TF-IDF index (`data/workspace` by default). |
| `GPTLOV_OPENAI_MODEL` | Overrides the chat completion model (default `gpt-4o-mini`). |
| `OPENAI_BASE_URL` | Point to a custom OpenAI-compatible endpoint. |

> Existing `LOVCHAT_*` environment variables are still honoured for backwards compatibility.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e .
```

Create the expected directories and copy the archives:

```bash
mkdir -p data/raw
cp ../lovdata-public-data/*.tar.bz2 data/raw/
```

## Build the index

```bash
gptlov build-index \
  --raw-dir data/raw \
  --workspace data/workspace
```

The command extracts the archives, chunks the HTML/XML documents, and saves a TF-IDF index at
`data/workspace/vector_store.pkl`.

### Prebuild the vector store locally (recommended for Render)

To avoid expensive indexing during deployment you can build the vector store once on your machine
and host it somewhere HTTP-accessible:

1. Run `gptlov build-index --raw-dir data/raw --workspace data/workspace --force` locally after
   downloading the Lovdata archives.
2. (Optional) Compress the result with `tar -czf vector_store.tar.gz -C data/workspace vector_store.pkl`.
3. Upload `vector_store.pkl` (or the archive) to object storage or any static hosting provider.
4. Set `GPTLOV_VECTOR_STORE_URL` to the download link. GPTLov supports direct `.pkl`, `.tar`,
   `.tar.gz`, `.tgz`, `.tar.bz2`, and `.zip` files and will download/extract the vector store at
   startup.

You can automate steps 1–3 with `scripts/prebuild_vector_store.py`, which builds the index, writes an
artifact (default `dist/vector_store.tar.gz`), and optionally uploads it to a provided URL.

### Using Elasticsearch instead of the TF-IDF store

If you set `GPTLOV_SEARCH_BACKEND=elasticsearch`, GPTLov will stream the chunks into an
Elasticsearch cluster instead of building the local TF-IDF matrix (which is useful on memory
constrained hosts such as Render Free web services). Provide the following additional environment
variables:

- `GPTLOV_ES_HOST` – e.g. `https://<user>:<password>@<your-elasticsearch-host>:9243`
- `GPTLOV_ES_INDEX` – index name to use (defaults to `gptlov`)
- (Optional) `GPTLOV_ES_USERNAME` / `GPTLOV_ES_PASSWORD` if you prefer to pass credentials separately
- (Optional) `GPTLOV_ES_VERIFY_CERTS=false` if you need to disable certificate verification

The `gptlov build-index` command will push chunks into Elasticsearch, and the chatbot will query the
index at runtime.

## Chat with GPTLov

Interactive mode:

```bash
gptlov chat --workspace data/workspace
```

Single question:

```bash
gptlov chat --workspace data/workspace --question "Hva er hjemmelen for forskrift X?"
```

GPTLov displays the generated answer (or the best matching excerpts) alongside the top sources used.

## Run the API server locally

GPTLov ships with a FastAPI application that exposes the chatbot via HTTP.

```bash
uvicorn gptlov.server:app --reload --port 8000
```

- `GET /health` – health probe returning `{ "status": "ok" }`
- `POST /ask` – accepts `{ "question": "...", "top_k": 5 }` and returns the generated answer with sources.

Visit `http://localhost:8000/docs` for the interactive Swagger UI.

## Experimental Labs UI (Elastic example adaptation)

The repository now includes an experimental user interface in `labs_app/` based on
Elastic's [chatbot RAG example](https://github.com/elastic/elasticsearch-labs/tree/main/example-apps/chatbot-rag-app).
It keeps the streaming chat UX from the sample app while delegating retrieval and answer
generation to `GPTLovBot`.

1. Build the React frontend (requires Node >= 18 and Yarn):
   ```bash
   cd labs_app/frontend
   yarn install
   REACT_APP_API_HOST=/api yarn build
   ```
   The build artefacts end up in `labs_app/frontend/build` which Flask serves as static files.
2. Start the Flask API (after activating your Python environment and installing the project):
   ```bash
   export FLASK_APP=labs_app.api.app
   flask run --debug --port 4000
   ```
   The server exposes `GET /health` and the streaming endpoint `POST /api/chat`. The backend
   will lazily prepare the GPTLov vector store on first use, so the initial request may take a
   short while while archives are downloaded or the store loads from disk.
3. Open `http://localhost:4000/` to try the labs experience. The chat panel streams responses and
   highlights matching sources in a collapsible panel.

For development you can run the React dev server instead:

```bash
cd labs_app/frontend
REACT_APP_API_HOST=http://localhost:4000/api yarn start
```

Feel free to customise the React components (`labs_app/frontend/src/`) or swap out the API host to
target a deployed GPTLov backend.

## Deploy to Render

1. Push this repository to GitHub (already under `Prosperaino/GPTLov`).
2. Log in to https://render.com and click **New +** → **Blueprint**. Select the repository and ensure Render sees the `render.yaml` file in the root.
3. Review the service configuration:
   - Environment: Python
   - Build command: `pip install --upgrade pip && pip install -e .`
   - Start command: `uvicorn gptlov.server:app --host 0.0.0.0 --port 10000`
   - Persistent disk is not required; Render provides an ephemeral disk for the vector store build on startup.
4. Add the environment variables:
   - `OPENAI_API_KEY` (optional but required for model-generated answers)
   - `GPTLOV_RAW_DATA_DIR=data/raw`
   - `GPTLOV_WORKSPACE_DIR=data/workspace`
   - (Optional) `GPTLOV_VECTOR_STORE_URL=https://…/vector_store.tar.gz` if you have prebuilt the index
   - (Optional) `GPTLOV_ARCHIVES` with a comma-separated list of Lovdata archive filenames if you want to override the defaults (`gjeldende-lover.tar.bz2,gjeldende-sentrale-forskrifter.tar.bz2`).

   If you decide to use an Elasticsearch cluster instead of the bundled TF-IDF store, also set:

   - `GPTLOV_SEARCH_BACKEND=elasticsearch`
   - `GPTLOV_ES_HOST=https://<user>:<password>@<your-elasticsearch-host>`
   - `GPTLOV_ES_INDEX=gptlov`
5. Click **Deploy**. On service startup GPTLov downloads the public Lovdata archives, pushes the chunks
   to Elasticsearch, and serves the API.

### Public URL `labs.prosper-ai.no/gptlov/`

Once the Render deployment is live and your reverse proxy/DNS is configured:

1. Point `labs.prosper-ai.no` at the Render service (via CNAME or the mechanism your DNS provider recommends).
2. Ensure the proxy forwards requests for `/gptlov/` (including `/gptlov/ask` and `/gptlov/static`) to the Render service without stripping the prefix.
3. Wait for DNS propagation and TLS issuance. Render will provision certificates automatically once the DNS resolves correctly.
4. Verify by browsing to `https://labs.prosper-ai.no/gptlov/`.

### Route multiple apps from `labs.prosper-ai.no`

The repository includes `cloudflare/worker.js`, a Cloudflare Worker that forwards different path prefixes on the `labs.prosper-ai.no` host to any backend (Render or otherwise). To use it:

1. Create a Worker on Cloudflare → paste the script from `cloudflare/worker.js`.
2. Add Worker environment variables for each origin you target (e.g. `GPTLOV_ORIGIN=https://<render-service>.onrender.com`).
3. Attach the Worker to the zone with a route such as `labs.prosper-ai.no/*`.
4. Extend the `ROUTES` array in the script for more applications, giving each a unique `prefix` and matching environment variable.
5. Ensure your DNS record for `labs.prosper-ai.no` is proxied (orange cloud) so requests flow through the Worker.
6. Visiting `https://labs.prosper-ai.no/` displays a minimal Prosper AI Labs placeholder directly from the Worker; override it if you prefer a different landing page. Routes without a trailing slash are automatically redirected (e.g. `/gptlov → /gptlov/`), and the Worker rewrites any root-relative asset URLs (`/static/...`) to include the prefix so CSS/JS load correctly.

## License

This project mirrors and interacts with content licensed under the Norwegian Licence for Open Data (NLOD 2.0).
Please review the Lovdata terms at https://api.lovdata.no/ before redistribution.
