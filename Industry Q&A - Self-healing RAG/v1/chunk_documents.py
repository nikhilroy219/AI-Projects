"""
Step 2 of the RAG pipeline: split extracted text into overlapping chunks.

Why chunk at all:
An embedding model can't usefully represent a 90,000-character document as
a single vector, and Claude's answers need to be grounded in a specific
passage, not "somewhere in this huge PDF." So we cut each document into
smaller pieces, each piece gets its own embedding later, and retrieval
finds the specific pieces relevant to a question instead of the whole file.

Why overlap:
If a sentence explaining something important sits right at a chunk boundary,
a hard cut can split it across two chunks and weaken both. A small overlap
(150 characters) means the tail of one chunk repeats as the head of the
next, so nothing important gets orphaned right at a cut point.

Method (kept deliberately simple for v1, no ML involved):
- Fixed-size sliding window over the raw text: 1000 characters per chunk,
  moving forward 850 characters each step (giving 150 characters of overlap)
- Snap the cut point to the nearest whitespace so we don't slice a word
  in half

Run with: python chunk_documents.py
"""

import json
from pathlib import Path

INPUT_DIR = Path("extracted_text")
OUTPUT_FILE = Path("chunks.json")

CHUNK_SIZE = 1000
OVERLAP = 150
STEP = CHUNK_SIZE - OVERLAP


def snap_to_whitespace(text: str, position: int) -> int:
    """Nudge a cut point forward to the next whitespace, so we don't cut mid-word."""
    if position >= len(text):
        return len(text)
    while position < len(text) and not text[position].isspace():
        position += 1
    return position


def chunk_text(text: str) -> list[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + CHUNK_SIZE, len(text))
        end = snap_to_whitespace(text, end)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start += STEP
    return chunks


def main():
    txt_files = sorted(INPUT_DIR.glob("*.txt"))
    if not txt_files:
        print(f"No .txt files found in {INPUT_DIR}/. Run extract_text.py first.")
        return

    all_chunks = []
    print(f"{'Document':<40} {'Chunks':>8}")
    print("-" * 50)

    for txt_path in txt_files:
        text = txt_path.read_text(encoding="utf-8")
        doc_chunks = chunk_text(text)

        for i, chunk in enumerate(doc_chunks):
            all_chunks.append({
                "id": f"{txt_path.stem}__chunk{i}",
                "source": txt_path.stem,
                "chunk_index": i,
                "text": chunk,
                "char_count": len(chunk),
            })

        print(f"{txt_path.name:<40} {len(doc_chunks):>8}")

    print("-" * 50)
    print(f"{'TOTAL':<40} {len(all_chunks):>8}")

    OUTPUT_FILE.write_text(json.dumps(all_chunks, indent=2), encoding="utf-8")
    print(f"\nSaved {len(all_chunks)} chunks to {OUTPUT_FILE}")

    print("\nSample chunk (chunk 5 of the first document):")
    sample = [c for c in all_chunks if c["source"] == txt_files[0].stem][5]
    print(f"--- {sample['id']} ({sample['char_count']} chars) ---")
    print(sample["text"][:400])


if __name__ == "__main__":
    main()
