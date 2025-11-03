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
   - `GPTLOV_SEARCH_BACKEND=elasticsearch`
   - `GPTLOV_ES_HOST=https://<user>:<password>@<your-elasticsearch-host>`
   - `GPTLOV_ES_INDEX=gptlov`
   - (Optional) `GPTLOV_ARCHIVES` with a comma-separated list of Lovdata archive filenames if you want to override the defaults (`gjeldende-lover.tar.bz2,gjeldende-sentrale-forskrifter.tar.bz2`).
5. Click **Deploy**. On service startup GPTLov downloads the public Lovdata archives, pushes the chunks
   to Elasticsearch, and serves the API.

### Custom domain `gptlov.no`

Once the Render deployment is live:

1. In the Render dashboard, open the GPTLov service → **Settings** → **Custom Domains** → **Add Custom Domain**.
2. Enter `gptlov.no` (and optionally `www.gptlov.no`). Render will show the required DNS target (a CNAME record pointing to `your-service.onrender.com`).
3. In your domain registrar's DNS control panel (where `gptlov.no` is registered), create:
   - A CNAME record for `www` pointing to the Render-provided hostname (e.g. `gptlov.onrender.com`).
   - If you want the apex (`gptlov.no` without `www`), add an ALIAS/ANAME record pointing to the same Render hostname, or use a URL redirect to `www.gptlov.no` if your registrar supports it.
4. Wait for DNS propagation (usually a few minutes). Render will automatically generate TLS certificates once the DNS records resolve correctly.
5. Verify by browsing to `https://gptlov.no`.

## License

This project mirrors and interacts with content licensed under the Norwegian Licence for Open Data (NLOD 2.0).
Please review the Lovdata terms at https://api.lovdata.no/ before redistribution.
