# Project Write-Up

## What it does

I built a question-answering system over 7 real EU and German energy policy documents, covering the REPowerEU plan, offshore wind strategy, grid infrastructure roadmaps, and electricity market data. I can ask it a real question, "what offshore wind capacity has the EU targeted for 2050?", and it retrieves the actual relevant passages from those documents and answers using only what it finds there, with the source cited. If the documents don't actually cover something I ask, it tells me honestly instead of guessing.

## Why RAG was the right approach

I didn't want a chatbot reciting general knowledge about energy policy, I wanted answers grounded in specific, real, current documents, with the ability to point to exactly where an answer came from. That's precisely what RAG is for: instead of relying on what a model happened to learn during training, it retrieves the actual relevant text at question time and builds the answer from that. It also means I can add new documents without retraining anything, I just re-run the ingestion pipeline.

## What the self-healing layer catches, and why it matters

A plain RAG system will confidently answer even when its retrieval was weak or its context was incomplete, because nothing is checking. I built a layer that checks two things before trusting an answer: whether the retrieved passages actually look relevant (a rerank-score threshold), and whether Claude itself judged its own answer as sufficiently grounded, not just plausible-sounding. If either check fails, the system retries once with a wider search before giving an honest "I don't have enough information" instead of a shaky answer. In testing, this caught a real case where the correct number was retrieved but presented with the wrong scope, and correctly refused two deliberately unrelated trap questions, all without ever fabricating an answer.

## One honest limitation

The self-healing retry only helps when a relevant chunk exists in the corpus but ranked outside the initial search window, it widens the net, so it can catch things the first pass missed. It cannot manufacture information that isn't in the documents at all. I confirmed this directly: asking about a topic genuinely outside the source material still correctly failed even after the retry, which is the right behavior, but it's worth being clear that "self-healing" means catching recoverable retrieval gaps, not compensating for a fundamentally missing document.
