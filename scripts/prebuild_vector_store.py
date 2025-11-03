#!/usr/bin/env python3
"""Build and package the GPTLov TF-IDF vector store locally.

Steps performed:
1. Runs `gptlov build-index` (forcing the sklearn/TF-IDF backend).
2. Packages the resulting `vector_store.pkl` into the requested artifact format.
3. Optionally uploads the artifact to a provided URL (e.g. S3 pre-signed URL).

Example:
    ./scripts/prebuild_vector_store.py \\
        --raw-dir data/raw \\
        --workspace data/workspace \\
        --artifact dist/vector_store.tar.gz \\
        --upload-url https://storage.example.com/presigned/url
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path
from typing import Iterable
from zipfile import ZIP_DEFLATED, ZipFile

try:
    import httpx  # type: ignore
except ModuleNotFoundError as exc:  # pragma: no cover
    raise SystemExit(
        "httpx is required to run this helper script. Install it with 'pip install httpx'."
    ) from exc

VECTOR_STORE_FILENAME = "vector_store.pkl"


def build_index(raw_dir: Path, workspace: Path, chunk_size: int, overlap: int, force: bool) -> None:
    env = os.environ.copy()
    env["GPTLOV_SEARCH_BACKEND"] = "sklearn"
    cmd: list[str] = [
        sys.executable,
        "-m",
        "gptlov.cli",
        "build-index",
        "--raw-dir",
        str(raw_dir),
        "--workspace",
        str(workspace),
        "--chunk-size",
        str(chunk_size),
        "--overlap",
        str(overlap),
    ]
    if force:
        cmd.append("--force")
    subprocess.run(cmd, check=True, env=env)


def _artifact_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pkl":
        return "pkl"
    if suffix == ".zip":
        return "zip"
    if suffix in {".gz", ".tgz", ".bz2"} and path.stem.endswith(".tar"):
        return "tar-compressed"
    if suffix == ".tar":
        return "tar"
    raise ValueError(f"Unsupported artifact extension for {path}")


def package_vector_store(store_path: Path, artifact_path: Path) -> Path:
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_type = _artifact_type(artifact_path)

    if artifact_type == "pkl":
        shutil.copy2(store_path, artifact_path)
    elif artifact_type == "zip":
        with ZipFile(artifact_path, "w", compression=ZIP_DEFLATED) as archive:
            archive.write(store_path, arcname=VECTOR_STORE_FILENAME)
    elif artifact_type in {"tar", "tar-compressed"}:
        mode = "w"
        if artifact_path.suffix == ".gz" or artifact_path.name.endswith(".tar.gz"):
            mode = "w:gz"
        elif artifact_path.suffix == ".bz2" or artifact_path.name.endswith(".tar.bz2"):
            mode = "w:bz2"
        elif artifact_path.suffix == ".tgz":
            mode = "w:gz"
        with tarfile.open(artifact_path, mode) as archive:
            archive.add(store_path, arcname=VECTOR_STORE_FILENAME)
    else:  # pragma: no cover - defensive
        raise ValueError(f"Unhandled artifact type for {artifact_path}")

    return artifact_path


def upload_artifact(
    artifact_path: Path,
    url: str,
    method: str = "PUT",
    headers: Iterable[str] | None = None,
) -> None:
    method = method.upper()
    prepared_headers = {}
    if headers:
        for header in headers:
            if ":" not in header:
                raise ValueError(f"Invalid header '{header}'. Expected 'Key: Value'.")
            key, value = header.split(":", 1)
            prepared_headers[key.strip()] = value.strip()

    file_size = artifact_path.stat().st_size
    print(f"Uploading {artifact_path} ({file_size / (1024 * 1024):.2f} MiB) to {url} ...")
    with artifact_path.open("rb") as handle:
        response = httpx.request(method, url, content=handle, headers=prepared_headers, timeout=None)
        response.raise_for_status()
    print(f"Upload complete (HTTP {response.status_code}).")


def main() -> None:
    parser = argparse.ArgumentParser(description="Prebuild the GPTLov vector store.")
    parser.add_argument("--raw-dir", default="data/raw", type=Path, help="Lovdata archive directory")
    parser.add_argument(
        "--workspace", default="data/workspace", type=Path, help="Directory for vector store"
    )
    parser.add_argument(
        "--artifact",
        default=Path("dist/vector_store.tar.gz"),
        type=Path,
        help="Output artifact path (.pkl, .tar, .tar.gz, .tar.bz2, .tgz, .zip)",
    )
    parser.add_argument("--chunk-size", type=int, default=1200, help="Words per chunk")
    parser.add_argument("--overlap", type=int, default=200, help="Word overlap between chunks")
    parser.add_argument("--force", action="store_true", help="Force rebuild even if data exists")
    parser.add_argument("--skip-build", action="store_true", help="Skip running gptlov build-index")
    parser.add_argument("--upload-url", help="Destination URL to upload the artifact")
    parser.add_argument(
        "--upload-method",
        default="PUT",
        help="HTTP method to use when uploading (default: PUT)",
    )
    parser.add_argument(
        "--upload-header",
        action="append",
        help="Extra header for upload in 'Key: Value' format (can be used multiple times)",
    )
    args = parser.parse_args()

    raw_dir: Path = args.raw_dir
    workspace: Path = args.workspace
    artifact_path: Path = args.artifact

    if not args.skip-build:
        print(f"Building vector store using archives in {raw_dir} ...")
        build_index(raw_dir, workspace, args.chunk_size, args.overlap, args.force)
    else:
        print("Skipping build step.")

    store_path = workspace / VECTOR_STORE_FILENAME
    if not store_path.exists():
        raise SystemExit(f"Vector store not found at {store_path}. Did the build step succeed?")

    print(f"Packaging vector store into {artifact_path} ...")
    packaged_path = package_vector_store(store_path, artifact_path)
    print(f"Artifact written to {packaged_path.resolve()}")

    if args.upload_url:
        upload_artifact(
            packaged_path,
            args.upload_url,
            method=args.upload_method,
            headers=args.upload_header,
        )
        print("Upload finished.")
    else:
        print("No upload URL provided; skipping upload step.")

    print("\nNext steps:")
    print(f"  1. Host the artifact (e.g. at {packaged_path}) on object storage with HTTPS access.")
    print("  2. Set GPTLOV_VECTOR_STORE_URL to the hosted location for your Render service.")
    print("  3. Redeploy the service; it will download the prebuilt vector store during startup.")


if __name__ == "__main__":
    main()
