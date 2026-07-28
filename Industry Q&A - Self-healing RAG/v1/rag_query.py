"""
Phase 1 (retrieval + generation) plus Phase 2 (self-healing) combined:
a command-line RAG system that catches its own weak answers instead of
confidently guessing.

Pipeline per question:
1. Retrieval  - embed the question, pull 20 candidate chunks from Chroma
   by vector similarity (fast, approximate).
2. Reranking  - a cross-encoder rereads the question against all 20 and
   rescores them properly, we keep the true top 5.
3. Self-healing check A (pre-generation): if even the best-scoring chunk
   from reranking looks like a weak match, we don't bother asking Claude,
   a weak match in means a weak answer out. Skip straight to retry.
4. Generation - the 5 chunks go to Claude with an instruction to answer
   ONLY from them, and to honestly flag if it didn't have enough to work
   with.
5. Self-healing check B (post-generation): if Claude flagged its own
   answer as insufficiently grounded, that's the second trigger.
6. Retry: on either check A or B failing, retry ONCE with a much wider
   net (40 candidates, top 8 kept instead of 20/5).
7. Fallback: if the retry is still weak or still ungrounded, give an
   honest "not enough information" answer instead of Claude's shaky one.

Every trigger point prints what's happening, this is deliberate, a
self-healing system that fails silently is worse than one that doesn't
self-heal at all, you'd never know to trust or distrust it.

Requires: an Anthropic API key set as an environment variable.
    $env:ANTHROPIC_API_KEY = "your-key-here"

Run with: python rag_query.py
"""

import os
import re
import sys

import chromadb
from anthropic import Anthropic
from sentence_transformers import CrossEncoder, SentenceTransformer

DB_DIR = "chroma_db"
COLLECTION_NAME = "energy_docs"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
CLAUDE_MODEL = "claude-sonnet-5"

# Normal first attempt
RETRIEVE_K = 20
FINAL_K = 5

# Wider retry, used only when the first attempt looks weak
RETRY_RETRIEVE_K = 40
RETRY_FINAL_K = 8

# Below this rerank score, we treat the best available chunk as a weak
# match. This is a starting heuristic, not a rigorously tuned number,
# we validate and adjust it with real test questions.
WEAK_RETRIEVAL_THRESHOLD = 0.5

FALLBACK_MESSAGE = (
    "I don't have enough information in these documents to answer that "
    "question confidently."
)

SYSTEM_PROMPT = """You are answering questions using only the provided document excerpts about European energy policy and grid infrastructure.

Rules:
- Answer using ONLY the information in the excerpts below. Do not use outside knowledge.
- If the excerpts don't contain enough information to answer, say so plainly, don't guess or fill gaps from general knowledge.
- When you use a fact from an excerpt, mention which source it came from.
- Be concise and direct.

At the very end of your answer, on its own new line, add exactly one of:
CONFIDENCE: SUFFICIENT
CONFIDENCE: INSUFFICIENT

Use INSUFFICIENT if the excerpts only partially covered the question, forced you to guess, or left real gaps, even if you were still able to write something. Use SUFFICIENT only if the excerpts genuinely answered the question."""


def retrieve(collection, embed_model, question, top_k):
    query_embedding = embed_model.encode([question], convert_to_numpy=True).tolist()
    results = collection.query(query_embeddings=query_embedding, n_results=top_k)

    chunks = []
    for i in range(len(results["ids"][0])):
        chunks.append({
            "id": results["ids"][0][i],
            "text": results["documents"][0][i],
            "source": results["metadatas"][0][i]["source"],
            "distance": results["distances"][0][i],
        })
    return chunks


def rerank(cross_encoder, question, chunks, top_k):
    pairs = [[question, c["text"]] for c in chunks]
    scores = cross_encoder.predict(pairs)

    for chunk, score in zip(chunks, scores):
        chunk["rerank_score"] = float(score)

    chunks_sorted = sorted(chunks, key=lambda c: c["rerank_score"], reverse=True)
    return chunks_sorted[:top_k]


def build_context(chunks):
    parts = []
    for c in chunks:
        parts.append(f"[Source: {c['source']}]\n{c['text']}")
    return "\n\n---\n\n".join(parts)


def extract_text(response):
    # Sonnet 5 thinks before answering by default, which adds a "thinking"
    # content block ahead of the actual answer. Find the text block instead
    # of assuming it's always first.
    for block in response.content:
        if block.type == "text":
            return block.text
    return ""


def generate_answer(client, question, chunks):
    """Returns (answer_text, confidence) where confidence is 'SUFFICIENT' or 'INSUFFICIENT'."""
    context = build_context(chunks)
    user_message = f"""Document excerpts:

{context}

Question: {question}"""

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    raw_text = extract_text(response)

    match = re.search(r"CONFIDENCE:\s*(SUFFICIENT|INSUFFICIENT)", raw_text)
    confidence = match.group(1) if match else "SUFFICIENT"

    # Strip the confidence tag out of what we show the user
    clean_text = re.sub(r"\n*CONFIDENCE:\s*(SUFFICIENT|INSUFFICIENT)\s*$", "", raw_text).strip()

    return clean_text, confidence


def print_scores(chunks):
    for c in chunks:
        print(f"    {c['source']:<35} rerank score: {c['rerank_score']:.2f}")


def try_answer(collection, embed_model, reranker, claude, question, retrieve_k, final_k):
    """One full attempt: retrieve, rerank, check, maybe generate, check again.

    Returns (answer_or_None, chunks, status) where status explains what
    happened: 'ok', 'weak_retrieval', or 'ungrounded'. answer is None
    whenever status isn't 'ok', signaling the caller to retry or fall back.
    """
    candidates = retrieve(collection, embed_model, question, top_k=retrieve_k)
    chunks = rerank(reranker, question, candidates, top_k=final_k)
    top_score = max((c["rerank_score"] for c in chunks), default=0.0)

    print(f"\n  (retrieved {len(candidates)} candidates, reranked to {len(chunks)}, best match score: {top_score:.2f})")
    print_scores(chunks)

    if top_score < WEAK_RETRIEVAL_THRESHOLD:
        return None, chunks, "weak_retrieval"

    answer, confidence = generate_answer(claude, question, chunks)
    print(f"  (Claude self-reported confidence: {confidence})")

    if confidence == "INSUFFICIENT":
        return None, chunks, "ungrounded"

    return answer, chunks, "ok"


def answer_question(collection, embed_model, reranker, claude, question):
    answer, chunks, status = try_answer(
        collection, embed_model, reranker, claude, question, RETRIEVE_K, FINAL_K
    )

    if status != "ok":
        reason = "the best-matching chunk was too weak" if status == "weak_retrieval" else "Claude flagged its own answer as insufficiently grounded"
        print(f"\n  \u26a0 Self-healing triggered: {reason}.")
        print(f"  Retrying with a wider search ({RETRY_RETRIEVE_K} candidates, top {RETRY_FINAL_K} kept)...")

        answer, chunks, status = try_answer(
            collection, embed_model, reranker, claude, question, RETRY_RETRIEVE_K, RETRY_FINAL_K
        )

        if status != "ok":
            print(f"  \u2717 Retry still {status.replace('_', ' ')}. Falling back to an honest response.\n")
            answer = FALLBACK_MESSAGE
        else:
            print("  \u2713 Retry succeeded.\n")

    return answer


def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY is not set. Run this first, in this same PowerShell window:")
        print('  $env:ANTHROPIC_API_KEY = "your-key-here"')
        sys.exit(1)

    print("Loading embedding model...")
    embed_model = SentenceTransformer(EMBEDDING_MODEL)

    print("Loading reranking model...")
    reranker = CrossEncoder(RERANK_MODEL)

    print("Connecting to vector database...")
    client_db = chromadb.PersistentClient(path=DB_DIR)
    try:
        collection = client_db.get_collection(COLLECTION_NAME)
    except Exception:
        print(f"Collection '{COLLECTION_NAME}' not found. Run build_vector_db.py first.")
        sys.exit(1)

    claude = Anthropic()

    print(f"\nReady. {collection.count()} chunks loaded. Ask a question, or type 'exit' to quit.\n")

    while True:
        question = input("Q: ").strip()
        if question.lower() in ("exit", "quit"):
            break
        if not question:
            continue

        answer = answer_question(collection, embed_model, reranker, claude, question)
        print(f"A: {answer}\n")


if __name__ == "__main__":
    main()
