"""
Step 3 of the RAG pipeline: turn each text chunk into an embedding (a vector
of numbers that captures its meaning).

Why this matters:
An embedding model maps text to a point in high-dimensional space such that
texts with similar meaning end up close together. Later, when someone asks
a question, we embed the question the same way and find the chunks whose
vectors sit closest to it, that's the "retrieval" half of RAG.

Which model, and why:
Anthropic does not offer its own embedding model, they officially recommend
Voyage AI for that. Voyage requires a separate API key and account. For this
prototype we're instead using a free, local, open-source model called
all-MiniLM-L6-v2 (via the sentence-transformers library). It runs entirely
on your machine, no extra account or API key needed, and it's a very
standard, well-tested choice for RAG projects.

This is a real architectural trade-off worth being able to explain: a
hosted embedding API (like Voyage) generally gives higher retrieval quality
and offloads compute, at the cost of a paid dependency and network calls.
A local model like this one is free and self-contained, at the cost of
somewhat lower embedding quality and using your own CPU. For a prototype
with 7 documents, local is the simpler and cheaper choice. A production
system handling far more documents and traffic would likely switch to a
hosted provider.

Run with: python generate_embeddings.py
(First run will download the model, ~90MB, one time only.)
"""

import json
import time
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

CHUNKS_FILE = Path("chunks.json")
EMBEDDINGS_FILE = Path("embeddings.npy")
MODEL_NAME = "all-MiniLM-L6-v2"


def main():
    if not CHUNKS_FILE.exists():
        print(f"{CHUNKS_FILE} not found. Run chunk_documents.py first.")
        return

    chunks = json.loads(CHUNKS_FILE.read_text(encoding="utf-8"))
    texts = [c["text"] for c in chunks]
    print(f"Loaded {len(texts)} chunks from {CHUNKS_FILE}")

    print(f"Loading embedding model: {MODEL_NAME} (first run downloads it)...")
    model = SentenceTransformer(MODEL_NAME)

    print("Generating embeddings...")
    start = time.time()
    embeddings = model.encode(
        texts,
        batch_size=32,
        show_progress_bar=True,
        convert_to_numpy=True,
    )
    elapsed = time.time() - start

    np.save(EMBEDDINGS_FILE, embeddings)

    print(f"\nDone in {elapsed:.1f} seconds")
    print(f"Embedding shape: {embeddings.shape[0]} chunks x {embeddings.shape[1]} dimensions")
    print(f"Saved to {EMBEDDINGS_FILE}")


if __name__ == "__main__":
    main()
