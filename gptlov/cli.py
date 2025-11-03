from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .bot import GPTLovBot
from .ingest import build_chunks, extract_archives
from .index import build_vector_store
from .search_backends import ElasticsearchBackend
from .settings import settings


def command_build_index(args: argparse.Namespace) -> None:
    raw_dir = Path(args.raw_dir).expanduser().resolve()
    workspace = Path(args.workspace).expanduser().resolve()
    extracted_root = workspace / "extracted"

    print(f"Using raw data directory: {raw_dir}")
    print(f"Workspace directory: {workspace}")
    extracted_dirs = extract_archives(raw_dir, extracted_root, force=args.force)
    print(f"Extracted {len(extracted_dirs)} archive folders")

    chunks = build_chunks(extracted_dirs, chunk_size=args.chunk_size, overlap=args.overlap)
    print(f"Created {len(chunks)} document chunks")

    if settings.search_backend == "elasticsearch":
        backend = ElasticsearchBackend(
            host=settings.es_host or "",
            index=settings.es_index,
            username=settings.es_username,
            password=settings.es_password,
            verify_certs=settings.es_verify_certs,
        )
        backend.index_documents(chunks, force=args.force)
        print(f"Indexed chunks into Elasticsearch index '{settings.es_index}'")
    else:
        store_path = build_vector_store(chunks, workspace)
        print(f"Vector store saved to {store_path}")


def format_answer(result: dict[str, object], top_sources: int) -> str:
    answer = str(result["answer"])
    contexts = result.get("contexts", [])
    lines = ["Svar:", answer, "\nKilder:"]
    for entry in contexts[:top_sources]:
        title = entry.get("title") or entry.get("refid") or entry.get("source_path")
        score = float(entry.get("score", 0.0))
        lines.append(f"- {title} (score={score:.3f})")
    return "\n".join(lines)


def command_chat(args: argparse.Namespace) -> None:
    workspace = Path(args.workspace).expanduser().resolve()
    store_path: Path | None = None

    if settings.search_backend == "elasticsearch":
        store_path = None
    else:
        store_path = Path(args.store).expanduser().resolve() if args.store else workspace / "vector_store.pkl"
        if not store_path.exists():
            print(f"Vector store not found at {store_path}. Run 'gptlov build-index' first.", file=sys.stderr)
            raise SystemExit(1)

    bot = GPTLovBot(store_path=store_path, model=args.model)

    if args.question:
        result = bot.ask(args.question, top_k=args.top_k)
        print(format_answer(result, args.sources))
        return

    print("GPTLov er klar! Skriv spørsmål om lover/forskrifter. Skriv 'exit' for å avslutte.")
    while True:
        try:
            question = input("\nDu: ")
        except (EOFError, KeyboardInterrupt):
            print("\nAvslutter.")
            break
        if not question:
            continue
        if question.lower().strip() in {"exit", "quit", "q"}:
            print("Ha det!")
            break
        result = bot.ask(question, top_k=args.top_k)
        print("\n" + format_answer(result, args.sources))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gptlov", description="Lovdata RAG chatbot")
    subparsers = parser.add_subparsers(dest="command")

    build_cmd = subparsers.add_parser("build-index", help="Extract archives and build the vector store")
    build_cmd.add_argument("--raw-dir", default=str(settings.raw_data_dir), help="Directory containing Lovdata archives")
    build_cmd.add_argument("--workspace", default=str(settings.workspace_dir), help="Directory to store extracted data and index")
    build_cmd.add_argument("--chunk-size", type=int, default=1200, help="Approximate words per chunk")
    build_cmd.add_argument("--overlap", type=int, default=200, help="Word overlap between chunks")
    build_cmd.add_argument("--force", action="store_true", help="Force re-extraction of archives")
    build_cmd.set_defaults(func=command_build_index)

    chat_cmd = subparsers.add_parser("chat", help="Open the interactive GPTLov assistant")
    chat_cmd.add_argument("--workspace", default=str(settings.workspace_dir), help="Directory containing the vector store")
    chat_cmd.add_argument("--store", help="Path to a specific vector store file")
    chat_cmd.add_argument("--question", help="Ask a single question and exit")
    chat_cmd.add_argument("--top-k", type=int, default=settings.top_k, help="Number of chunks to retrieve")
    chat_cmd.add_argument("--model", help="OpenAI model name to use for generation")
    chat_cmd.add_argument("--sources", type=int, default=3, help="Number of sources to display in output")
    chat_cmd.set_defaults(func=command_chat)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not hasattr(args, "func"):
        parser.print_help()
        return

    args.func(args)


if __name__ == "__main__":  # pragma: no cover
    main()
