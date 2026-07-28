# Industry Intelligence Q&A: Self-Healing RAG

A retrieval-augmented Q&A system that answers questions using only what it can find and cite in a set of source documents, and says so honestly when it can't find enough, instead of guessing. Built twice: once from scratch in raw Python to show the underlying mechanics end-to-end, once with LangChain and LangGraph to show the same system using production-grade tooling.

This instance is grounded in 7 EU and German energy policy documents, but the pipeline is domain-agnostic - point it at any set of documents an organization can't hand to a general-purpose chatbot (internal policy, compliance filings, technical manuals, product documentation) and it answers the same way: grounded, cited, and honest about its own limits.

## What It Does

Ask it a real question about EU energy policy, offshore wind targets, grid infrastructure, or electricity markets, and it retrieves the actual relevant passages from source documents and answers using only what it finds there, with the source cited. If the documents don't cover something, it says so instead of guessing.

On every question, it:

1. Embeds the question and pulls the 20 closest-matching chunks from a vector database (fast, approximate)
2. Reranks those 20 with a cross-encoder that actually reads the question against each chunk, keeps the true top 5 (slower, accurate)
3. Checks whether even the best-matching chunk looks weak, before spending an API call on it
4. Sends the top chunks to Claude, instructed to answer only from that context and self-report whether it actually had enough to work with
5. If either check fails, retries once with a wider search (40 candidates, top 8 kept)
6. If it's still weak or still ungrounded after that, returns an honest "I don't have enough information in these documents" instead of a shaky answer

## Pipeline Architecture

```
Question
└── Embed question (same model used on the documents)
    └── Vector search (top 20 candidates)
        └── Rerank with cross-encoder (keep top 5)
            ├── [best score below threshold] Widen search (40 candidates, top 8)
            │   └── Rerank again
            │       ├── [still weak] -> Honest fallback: "not enough information"
            │       └── [strong]     -> Generate answer
            └── [strong match] Generate answer (Claude, context-only)
                ├── [Claude self-reports INSUFFICIENT] Widen search, retry once
                │   ├── [still insufficient] -> Honest fallback
                │   └── [sufficient]         -> Return answer
                └── [Claude self-reports SUFFICIENT] -> Return answer
```

Key design decisions:

- Reranking is a separate, slower pass on top of fast vector search, not a replacement for it, catches relevant chunks that similarity search alone ranked too low
- The retrieval-quality check runs before generation, a weak match skips the Claude call entirely rather than wasting one on a doomed answer
- Claude is instructed to self-report its own confidence, not just asked to answer, this is what makes the groundedness check possible
- Exactly one retry, then an honest failure, self-healing is meant to catch recoverable gaps, not mask a genuinely missing document
- Every self-healing trigger prints what happened and why, nothing about this fails silently

## Two Versions, One Repo

- **`v1/`** - built from scratch in raw Python, no RAG framework. Every step, chunking, embedding, similarity search, prompt construction, retry logic, is hand-written and explicit, so I can actually explain every mechanical piece rather than have a framework abstract it away.
- **`v2/`** - the same system rebuilt with LangChain for the retrieval/generation pipeline, and LangGraph specifically for the self-healing retry loop. LangGraph earns its place here because the retry is a genuine loop (check a condition, maybe go back and try again), and a plain LangChain chain can only move forward in a straight line.

## Stack

### v1 (Manual)

| Tool | Purpose |
|---|---|
| pypdf | PDF text extraction |
| Hand-written sliding window | Chunking (1000 chars, 150 overlap) |
| sentence-transformers (`all-MiniLM-L6-v2`) | Local embeddings, no API key needed |
| ChromaDB | Local vector database |
| cross-encoder (`ms-marco-MiniLM-L-6-v2`) | Reranking |
| Anthropic Claude (`claude-sonnet-5`) | Answer generation |

### v2 (LangChain + LangGraph)

| Tool | Purpose |
|---|---|
| `PyPDFLoader` | PDF text extraction |
| `RecursiveCharacterTextSplitter` | Chunking (same size/overlap as v1) |
| `HuggingFaceEmbeddings` (`all-MiniLM-L6-v2`) | Same embedding model as v1, wrapped |
| `langchain-chroma` | Same vector database, LangChain integration |
| `HuggingFaceCrossEncoder` | Same reranker as v1, wrapped |
| `ChatAnthropic` (`claude-sonnet-5`) | Same model as v1, wrapped |
| `LangGraph` `StateGraph` | Self-healing retry loop, the one part that's a genuine loop, not a chain |

## Setup

### Prerequisites

- Python 3.11+
- An Anthropic API key

### Installation

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r v1/v1_requirements.txt
pip install -r v2/v2_requirements.txt
```

Both versions share this one environment and reuse the same 7 source PDFs, stored once in `v1/source_docs/`.

Set your API key before running either version (session only, never saved to a file):
```powershell
$env:ANTHROPIC_API_KEY = "your-key-here"
```

## How to Use

**v1:**
```powershell
cd v1
python extract_text.py
python chunk_documents.py
python generate_embeddings.py
python build_vector_db.py
python rag_query.py
```

**v2:**
```powershell
cd v2
python build_index.py
python rag_query.py
```

The first steps in each build the database once, or whenever source documents change. `rag_query.py` is the actual question-answering loop, ask anything, type `exit` to quit.

## Test Results

11+ real test questions run against v1, including two deliberately adversarial trap questions and one real bug found and fixed mid-project, are logged with full results in `v1/test_questions_log.md`. A representative subset was validated against v2 to confirm functional parity, documented in the same file.

See `WRITEUP.md` for the short plain-language summary: what it does, why RAG was the right approach, what the self-healing layer actually catches, and one honest limitation.

---

Built by [Nikhil Roy](https://nikhilroy.lovable.app), Berlin
