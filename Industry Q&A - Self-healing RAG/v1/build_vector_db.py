"""
Step 4 of the RAG pipeline: store the chunks and their embeddings in a
local vector database (Chroma), so we can search them later.

Why a vector database at all:
We now have 660 chunks and 660 embeddings sitting in separate files
(chunks.json, embeddings.npy). A vector database's job is to index those
embeddings so that, given a new vector (a question's embedding), it can
instantly find the closest matches without comparing against all 660 by
hand every time. Chroma does this locally, no server or account needed,
it just writes files to a folder on disk (chroma_db/).

Note: we're passing in embeddings we already computed with
generate_embeddings.py, rather than letting Chroma generate its own. This
is deliberate for v1, we want every step of the pipeline to be an explicit,
visible line of code we can point to and explain, not something a library
does automatically behind the scenes.

Production-scale note (for the write-up):
Chroma running locally is perfect for a prototype like this one. A
production system with millions of chunks and many concurrent users would
typically use a managed vector database (Pinecone, Weaviate, or pgvector)
instead, for scalability and reliability reasons. That swap wouldn't change
anything else in this pipeline, it's a drop-in replacement for this one step.

Run with: python build_vector_db.py
"""

import json
from pathlib import Path

import chromadb
import numpy as np

CHUNKS_FILE = Path("chunks.json")
EMBEDDINGS_FILE = Path("embeddings.npy")
DB_DIR = "chroma_db"
COLLECTION_NAME = "energy_docs"


def main():
    if not CHUNKS_FILE.exists() or not EMBEDDINGS_FILE.exists():
        print("Missing chunks.json or embeddings.npy. Run the previous two scripts first.")
        return

    chunks = json.loads(CHUNKS_FILE.read_text(encoding="utf-8"))
    embeddings = np.load(EMBEDDINGS_FILE)

    if len(chunks) != len(embeddings):
        print(f"Mismatch: {len(chunks)} chunks but {len(embeddings)} embeddings. Re-run generate_embeddings.py.")
        return

    print(f"Loaded {len(chunks)} chunks and matching embeddings")

    client = chromadb.PersistentClient(path=DB_DIR)

    # Start fresh each time this script runs, avoids duplicate entries
    # if we re-run it after changing chunking or documents.
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass
    collection = client.create_collection(COLLECTION_NAME)

    ids = [c["id"] for c in chunks]
    documents = [c["text"] for c in chunks]
    metadatas = [{"source": c["source"], "chunk_index": c["chunk_index"]} for c in chunks]

    # Chroma wants embeddings as plain lists, not numpy arrays
    embeddings_list = embeddings.tolist()

    # Add in batches to keep memory use reasonable
    batch_size = 100
    for i in range(0, len(ids), batch_size):
        end = i + batch_size
        collection.add(
            ids=ids[i:end],
            documents=documents[i:end],
            embeddings=embeddings_list[i:end],
            metadatas=metadatas[i:end],
        )

    print(f"Stored {collection.count()} chunks in Chroma collection '{COLLECTION_NAME}'")
    print(f"Database saved to ./{DB_DIR}/")

    # Quick sanity check: query with the first chunk's own embedding,
    # it should retrieve itself as the top result.
    print("\nSanity check: searching with chunk 0's own embedding...")
    result = collection.query(
        query_embeddings=[embeddings_list[0]],
        n_results=3,
    )
    print("Top match ID:", result["ids"][0][0], "(should match:", ids[0], ")")
    print("Top 3 matches:", result["ids"][0])


if __name__ == "__main__":
    main()
