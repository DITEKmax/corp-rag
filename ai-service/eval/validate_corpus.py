from __future__ import annotations

import argparse
from pathlib import Path

from eval.io import compute_corpus_hash, corpus_document_paths, load_corpus_metadata, load_manifest

DEFAULT_CORPUS_DIR = Path(__file__).resolve().parent / "corpus"
DEFAULT_META_PATH = Path(__file__).resolve().parent / "golden" / "golden_ru.meta.json"


def validate_corpus(corpus_dir: Path = DEFAULT_CORPUS_DIR, meta_path: Path = DEFAULT_META_PATH) -> dict[str, object]:
    manifest_path = corpus_dir / "manifest.json"
    manifest = load_manifest(manifest_path)
    metadata = load_corpus_metadata(meta_path)
    if manifest.language != "ru" or metadata.language != "ru":
        raise ValueError("Phase 7 scored corpus must be Russian")
    if len(manifest.documents) != 16:
        raise ValueError(f"expected exactly 16 corpus documents, found {len(manifest.documents)}")
    paths = corpus_document_paths(corpus_dir, manifest)
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise ValueError(f"missing corpus files: {missing}")
    empty = [str(path) for path in paths if not path.read_text(encoding="utf-8").strip()]
    if empty:
        raise ValueError(f"empty corpus files: {empty}")
    actual_hash = compute_corpus_hash(corpus_dir, manifest)
    if actual_hash != metadata.corpus_hash:
        raise ValueError(f"corpus hash mismatch: metadata={metadata.corpus_hash} actual={actual_hash}")
    if metadata.document_count != 16:
        raise ValueError("metadata document_count must be 16")
    return {
        "corpus_version": metadata.corpus_version,
        "corpus_hash": actual_hash,
        "document_count": len(paths),
        "indexed": metadata.indexed,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate the frozen Phase 7 Russian corpus snapshot.")
    parser.add_argument("--corpus-dir", type=Path, default=DEFAULT_CORPUS_DIR)
    parser.add_argument("--meta", type=Path, default=DEFAULT_META_PATH)
    args = parser.parse_args()
    result = validate_corpus(args.corpus_dir, args.meta)
    print(result)


if __name__ == "__main__":
    main()
