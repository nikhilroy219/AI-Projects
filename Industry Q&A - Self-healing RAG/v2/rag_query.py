"""
v2, query step: the LangChain + LangGraph rebuild of v1's rag_query.py.

Same retrieve -> rerank -> generate -> self-heal logic as v1, same models,
same thresholds, same retry strategy, just expressed as a graph instead of
hand-written if/else control flow.

Why LangGraph specifically, and not just LangChain, for this file:
the self-healing retry is a LOOP, retrieve, check, and if it's weak, go
back and retrieve again with wider settings. A plain LangChain chain can
only move forward in a straight line, it cannot loop back to an earlier
step. LangGraph models the app as a graph of nodes and edges instead, and
edges are allowed to point backwards, which is exactly what a retry needs.
That loop-back edge (widen -> retrieve_and_rerank, below) is the one line
of this file that plain LangChain genuinely cannot express.

One implementation note worth knowing: LangChain's built-in reranker
wrapper (CrossEncoderReranker) sorts documents by score internally but
doesn't hand the scores back out, it only returns the filtered documents.
Since our pre-generation check specifically needs to inspect the actual
score, we use the underlying HuggingFaceCrossEncoder.score() directly
instead of that higher-level wrapper. Still a LangChain class, just one
level closer to the model, because the convenience wrapper hides exactly
the number we need.

Also note: response.text (used below) is LangChain's own built-in fix for
the same "thinking block" bug we found and patched by hand in v1, it
automatically filters out non-text content blocks for us.

Run with: python rag_query.py
"""

import os
import re
import sys
from typing import TypedDict

from langchain_anthropic import ChatAnthropic
from langchain_chroma import Chroma
from langchain_community.cross_encoders import HuggingFaceCrossEncoder
from langchain_core.prompts import ChatPromptTemplate
from langchain_huggingface import HuggingFaceEmbeddings
from langgraph.graph import END, START, StateGraph

DB_DIR = "chroma_db"
COLLECTION_NAME = "energy_docs"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
CLAUDE_MODEL = "claude-sonnet-5"

RETRIEVE_K = 20
FINAL_K = 5
RETRY_RETRIEVE_K = 40
RETRY_FINAL_K = 8
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

prompt_template = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    ("human", "Document excerpts:\n\n{context}\n\nQuestion: {question}"),
])


class RAGState(TypedDict):
    question: str
    retrieve_k: int
    final_k: int
    attempt: int
    chunks: list  # list of (Document, score) tuples
    top_score: float
    answer: str
    confidence: str


def build_graph(vectorstore, cross_encoder, claude):

    def retrieve_and_rerank(state: RAGState) -> dict:
        candidates = vectorstore.similarity_search(state["question"], k=state["retrieve_k"])
        pairs = [(state["question"], doc.page_content) for doc in candidates]
        scores = cross_encoder.score(pairs)

        ranked = sorted(zip(candidates, scores), key=lambda x: x[1], reverse=True)
        chunks = ranked[:state["final_k"]]
        top_score = chunks[0][1] if chunks else 0.0

        print(f"\n  (retrieved {len(candidates)} candidates, reranked to {len(chunks)}, best match score: {top_score:.2f})")
        for doc, score in chunks:
            print(f"    {doc.metadata.get('source', '?'):<35} rerank score: {score:.2f}")

        return {"chunks": chunks, "top_score": top_score}

    def generate(state: RAGState) -> dict:
        context = "\n\n---\n\n".join(
            f"[Source: {doc.metadata.get('source', '?')}]\n{doc.page_content}"
            for doc, _ in state["chunks"]
        )
        messages = prompt_template.format_messages(context=context, question=state["question"])
        response = claude.invoke(messages)
        raw_text = response.text

        match = re.search(r"CONFIDENCE:\s*(SUFFICIENT|INSUFFICIENT)", raw_text)
        confidence = match.group(1) if match else "SUFFICIENT"
        clean_text = re.sub(r"\n*CONFIDENCE:\s*(SUFFICIENT|INSUFFICIENT)\s*$", "", raw_text).strip()

        print(f"  (Claude self-reported confidence: {confidence})")

        return {"answer": clean_text, "confidence": confidence}

    def widen(state: RAGState) -> dict:
        print(f"\n  \u26a0 Self-healing triggered. Retrying with a wider search ({RETRY_RETRIEVE_K} candidates, top {RETRY_FINAL_K} kept)...")
        return {"retrieve_k": RETRY_RETRIEVE_K, "final_k": RETRY_FINAL_K, "attempt": state["attempt"] + 1}

    def fallback(state: RAGState) -> dict:
        print("  \u2717 Retry did not resolve it. Falling back to an honest response.\n")
        return {"answer": FALLBACK_MESSAGE}

    def route_after_retrieval(state: RAGState) -> str:
        if state["top_score"] < WEAK_RETRIEVAL_THRESHOLD:
            return "fallback" if state["attempt"] > 0 else "widen"
        return "generate"

    def route_after_generation(state: RAGState) -> str:
        if state["confidence"] == "INSUFFICIENT":
            return "fallback" if state["attempt"] > 0 else "widen"
        return "end"

    graph = StateGraph(RAGState)
    graph.add_node("retrieve_and_rerank", retrieve_and_rerank)
    graph.add_node("generate", generate)
    graph.add_node("widen", widen)
    graph.add_node("fallback", fallback)

    graph.add_edge(START, "retrieve_and_rerank")
    graph.add_conditional_edges("retrieve_and_rerank", route_after_retrieval, {
        "generate": "generate",
        "widen": "widen",
        "fallback": "fallback",
    })
    graph.add_conditional_edges("generate", route_after_generation, {
        "widen": "widen",
        "fallback": "fallback",
        "end": END,
    })
    graph.add_edge("widen", "retrieve_and_rerank")  # the loop-back edge
    graph.add_edge("fallback", END)

    return graph.compile()


def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY is not set. Run this first, in this same PowerShell window:")
        print('  $env:ANTHROPIC_API_KEY = "your-key-here"')
        sys.exit(1)

    print("Loading embedding model...")
    embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)

    print("Loading reranking model...")
    cross_encoder = HuggingFaceCrossEncoder(model_name=RERANK_MODEL)

    print("Connecting to vector database...")
    vectorstore = Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=DB_DIR,
    )

    claude = ChatAnthropic(model=CLAUDE_MODEL, max_tokens=1024)

    app = build_graph(vectorstore, cross_encoder, claude)

    count = len(vectorstore.get()["ids"])
    print(f"\nReady. {count} chunks loaded. Ask a question, or type 'exit' to quit.\n")

    while True:
        question = input("Q: ").strip()
        if question.lower() in ("exit", "quit"):
            break
        if not question:
            continue

        result = app.invoke({
            "question": question,
            "retrieve_k": RETRIEVE_K,
            "final_k": FINAL_K,
            "attempt": 0,
        })
        print(f"A: {result['answer']}\n")


if __name__ == "__main__":
    main()
