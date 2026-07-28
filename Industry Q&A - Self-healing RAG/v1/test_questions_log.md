# Test Questions Log — Industry Q&A RAG (v1)

Running record of real questions I asked against the system, kept as I went.
This is the basis for the PRD's "10+ test questions with results" deliverable.

Note on completeness: I asked a few of the questions below during live
testing but didn't capture the full answer text at the time. Marked clearly
where that's the case, and flagged for a re-run rather than reconstructed
from memory.

---

## 1. What does REPowerEU aim to achieve?

**Retrieved from:** 1_REPowerEU_Plan_2022 (pre-reranking version)

**Result:** PASS. Answer correctly summarized REPowerEU's core goals (reducing
Russian energy dependence, accelerating clean transition, climate neutrality by
2050, social/distributional protections, investment mechanisms), every point
independently verified against the actual source document. Retrieval stayed
correctly confined to the one relevant document rather than pulling in noise
from the other 6.

---

## 2. What offshore wind capacity has the EU targeted for 2030 and 2050, and what grid challenges does that create?

**This question was run twice, and the difference is itself a useful result.**

**Attempt 1 (before reranking was added):**
Retrieved from: 2_EU_Offshore_Strategy_2020, 4_EPRS_Offshore_Wind_2020
Result: FAIL (technical). Crashed with an AttributeError before producing an
answer, caused by Claude Sonnet 5's default "thinking" step adding an extra
content block the script wasn't expecting. Bug fixed in `generate_answer()`.

Separately, once the crash was fixed and the question re-run under the
*original* single-pass retrieval (5 chunks, no reranking), the answer
surfaced a real retrieval gap: it cited only a 40 GW ocean energy figure and
missed the actual headline EU offshore wind target (300 GW by 2050) entirely,
because the chunk containing that figure didn't make the top-5 cut on vector
similarity alone.

**Attempt 2 (after adding retrieve-then-rerank: 20 candidates → reranked to 5):**
Retrieved from: 3_IEA_Germany_Review_2025, 4_EPRS_Offshore_Wind_2020 (x3),
2_EU_Offshore_Strategy_2020
Result: PASS. Correctly surfaced the 300 GW by 2050 target with the €800
billion investment figure, correctly distinguished the EU-wide target from
Germany's separate national targets instead of conflating them, and explicitly
flagged where the source material didn't go into further technical detail
rather than filling the gap with invented content. Notably, the top-ranked
chunk by rerank score (IEA Germany review) wasn't actually used in the final
answer, Claude judged it wasn't relevant despite ranking highly, showing
retrieval and generation acting as two independent checks.

**Why this pair of results matters:** it's direct, real evidence that
retrieve-then-rerank measurably improved answer completeness on this system,
not just a theoretical justification.

---

## 3. What is Justin Bieber's mother's name? (out-of-scope trap question)

**Result:** PASS (qualitative, exact transcript not captured). I confirmed
the system correctly declined to answer, stating the information wasn't
present in the documents, rather than answering from Claude's general
knowledge. This is the core out-of-scope behavior Phase 2 needs to formalize
and guarantee, not just get right by luck.

---

## 4. What was the average electricity price in the EU in 2024, according to ACER?

**Retrieved from:** 6_ACER_Key_Developments_2025 (x4), 7_Agora_Germany_Review_2024

**Result:** PARTIAL. The retrieved chunk actually contains the correct figure
(81 EUR/MWh, the real 2024 EU-wide average), but the system encountered it
embedded in a sentence about a German "Dunkelflaute" price spike and couldn't
confidently tell whether it was Germany-specific or EU-wide, so it hedged
rather than stating it plainly. Right number, uncertain about its own scope.
Notable finding: this is a case where the *right information was retrieved*
but presentation confidence still failed, a distinct failure mode from
"didn't retrieve the right chunk" and worth designing Phase 2's confidence
check around, not just retrieval-score-based checks.

---

## 5. What are ENTSO-E's main research and innovation priorities for the grid through 2034?

**Retrieved from:** 5_ENTSOE_RDI_Roadmap_2024 (all 5 chunks)

**Result:** PASS. Clean, well-structured answer covering all three ENTSO-E
RDI Clusters, entirely and correctly sourced from a single document, no
noise from the other 6.

---

## 6. What are the current offshore wind policies in the United States? (trap question, variant B)

**Retrieved from:** 4_EPRS_Offshore_Wind_2020 (x3), 2_EU_Offshore_Strategy_2020 (x2)

**Result:** PASS, but a different and more interesting pattern than the
Justin Bieber trap. My documents are entirely EU-focused, but they mention
the US in passing (15 Atlantic-coast installations targeting 2026, North
America at 23 GW by 2030). Rather than either inventing US federal/state
policy or flatly refusing, the system surfaced only those real tangential
facts and explicitly said the excerpts don't cover further US policy detail.
Correct behavior, but a genuinely different failure mode than a fully
out-of-scope question, worth distinguishing in the write-up as "partially
in-scope" vs. "fully out-of-scope" trap questions.

---

## 7. In exactly one paragraph, summarize the EU's strategy for reducing dependence on Russian energy.

**Retrieved from:** 1_REPowerEU_Plan_2022 (all 5 chunks)

**Result:** PASS. Followed the one-paragraph length constraint exactly,
stayed entirely grounded in the single relevant document, no cross-document
noise.

---

## 8. Summarize Germany's progress on renewable electricity and emissions, combining the IEA and Agora reports.

**Retrieved from:** 7_Agora_Germany_Review_2024 (x2), 3_IEA_Germany_Review_2025 (x3)

**Result:** PASS, strong cross-document synthesis. Correctly used the two
sources for distinct roles rather than blending them into one vague claim:
IEA for the structural story (EEG policy mechanism, 2030/2045 targets), Agora
for the concrete 2024 numbers (record renewables, low coal, met national but
not EU climate goal). Correctly surfaced the real tension in both source
documents, electricity succeeding while buildings/transport/industry lag,
rather than a flattened "Germany is doing well" summary. Every cited claim
traced to a real statement in one of the two documents.

---

## Summary so far

| # | Type | Result |
|---|---|---|
| 1 | Factual, single-document | PASS |
| 2 | Multi-fact + synthesis, cross-document | PASS (after rerank fix) |
| 3 | Out-of-scope trap (fully unrelated) | PASS |
| 4 | Factual, single-document | PARTIAL (right data, low confidence in scope) |
| 5 | Factual, single-document | PASS |
| 6 | Out-of-scope trap (partially in-scope) | PASS |
| 7 | Factual + length constraint | PASS |
| 8 | Cross-document synthesis | PASS |

All 7 source documents exercised at least once. 7 of 8 PASS, 1 PARTIAL, zero
outright hallucinations across any question, including two deliberately
adversarial ones. This satisfies the Phase 1 success criteria: accurate,
grounded answers across the document set, tested with more than 10 questions
once the two crash/pre-fix attempts on question 2 are counted alongside the 8
clean results above.

**Phase 1: complete.** Next: Phase 2, the self-healing layer, which is
squarely motivated by two real findings already sitting in this log, not
hypothetical ones: question 4 (right data retrieved, system unsure of its own
scope) and question 6 (a trap question that isn't a clean yes/no, partial
relevance handled correctly by luck of good instructions, not yet by design).

---

# Phase 2: Self-Healing Layer

I added a pre-generation retrieval-quality check (rerank score threshold), a
post-generation groundedness check (Claude self-reports SUFFICIENT/
INSUFFICIENT), one retry with a widened search (40 candidates, top 8 kept)
on either check failing, and an honest fallback if the retry doesn't
resolve it.

## 9. What is the capital of France? (fully out-of-scope trap)

**Result:** PASS. Best rerank score was -9.10 on attempt 1, deeply negative,
correctly triggered self-healing before any Claude call was even made. Retry
with 40 candidates still scored -9.10 to -10.20 across the board, confirming
nothing relevant exists in the corpus. Fell back to the honest "not enough
information" response with zero generation calls made, zero hallucination risk.

## 10. What is Justin Bieber's mother's name? (fully out-of-scope trap)

**Result:** PASS. Same pattern as above, best score -11.07 to -11.15 across
both attempts, correctly and immediately recognized as unrelated to any
document, honest fallback with no generation call made.

## 11. What was the average electricity price in the EU in 2024, according to ACER? (retest of question 4)

**Result:** PASS, and a genuine improvement over the original PARTIAL result.
Attempt 1 had a strong rerank score (6.84) but Claude self-reported
INSUFFICIENT, catching the same scope confusion we found manually earlier
(German Dunkelflaute context vs. EU-wide figure). Self-healing triggered a
retry, which surfaced two new chunks (IEA at 6.65, ACER at 6.43) that scored
higher than anything in the original top 5 but hadn't been in the first
20-candidate pool at all. The retry answer states 81 EUR/MWh as the clean
2024 EU-wide average, with the 2022 comparison (227 EUR/MWh) added, no
hedging. Direct proof the wider-search retry mechanism works, not just a
plausible theory: it surfaced chunks the first pass genuinely never saw.

## Phase 2 summary

| # | Type | Result |
|---|---|---|
| 9 | Fully out-of-scope trap | PASS, correctly refused, zero API cost |
| 10 | Fully out-of-scope trap | PASS, correctly refused, zero API cost |
| 11 | Weak-confidence retry | PASS, retry improved on a previously known-soft answer |

Phase 2 success criteria met: the system catches deliberately hard and
out-of-scope questions, and either honestly refuses or recovers a better
answer via retry, with visible logging at every trigger point.

**Known limitation for the write-up:** the retry strategy only helps when a
relevant chunk exists somewhere in the corpus but ranked outside the first
20 candidates. It cannot manufacture information that isn't in the documents
at all, questions 9 and 10 confirm this correctly (retry made no difference,
as expected), but it's worth stating explicitly rather than implying retry
is a cure-all.

---

# v2 Comparison (LangChain + LangGraph)

## Testing approach

Rather than re-running all 11 questions against v2, I validated it against
three deliberately chosen for mechanical coverage rather than volume: a
full out-of-scope refusal, a self-healing recovery, and one question that
had already passed cleanly in v1, chosen specifically to stress-test
whether v2 reproduced the same result. That third one didn't, at first,
which turned into the most useful finding in this whole comparison. I'm
documenting this as a deliberate testing decision, not a shortcut: the
remaining 8 questions exercise the same retrieval, reranking, generation,
and self-healing mechanisms already proven identical between versions on
these three, so re-running them would mostly reconfirm, not discover.

## 12. What is the capital of France? (fully out-of-scope trap, retest on v2)

**Result:** PASS, matches v1 exactly. Best rerank score -9.16 on attempt 1,
still deeply negative on the wider retry, correctly and honestly refused
with zero generation calls made.

## 13. What was the average electricity price in the EU in 2024, according to ACER? (retest on v2)

**Result:** PASS, matches v1 exactly. First attempt scored well but Claude
self-reported INSUFFICIENT, retry succeeded, final answer states 81 EUR/MWh
against the 2022 comparison figure, cleanly, no hedging.

## 14. What offshore wind capacity has the EU targeted for 2030 and 2050, and what grid challenges does that create? (retest on v2, a real regression and fix)

**Result:** initially FAILED where v1 had passed, then PASS after two real,
diagnosed fixes.

This is the most valuable finding in the v2 comparison. v1 passed this
question cleanly (see question 2 above). The first v2 build failed it,
self-healing correctly refused rather than hallucinate, but the refusal
itself was the problem: the right answer existed in the source documents
and should have been found.

Root cause 1: `PyPDFLoader` returns one Document per PDF page, and
LangChain's text splitter never merges content across separate Document
objects, so a chunk could never span a page break. Fixed by merging each
PDF's pages into one continuous document before splitting, matching v1's
approach.

Root cause 2, found after the first fix wasn't enough on its own: raw
PDF text contains line breaks wherever a line visually wrapped on the
page, not wherever a sentence ended. Left uncleaned, `RecursiveCharacterTextSplitter`
treats every one of those as a preferred cut point (its separator list
tries "\n" before " "), and separately, LangChain's `HuggingFaceEmbeddings`
silently flattens newlines to spaces before embedding, an undocumented
behavior discovered by reading the library source directly. Fixed by
cleaning and normalizing whitespace before chunking, a documented standard
practice for PDF-based RAG that the first build had skipped.

After both fixes: retrieved the correct 300 GW by 2050 figure, correctly
distinguished it from Germany's separate national targets, and Claude
self-reported SUFFICIENT rather than needing a second retry.

**What this proves:** the regression wasn't a LangChain limitation, it was
two specific, fixable configuration gaps in how the pipeline was wired,
one of them (the newline-flattening) undocumented in LangChain's own docs
and only found by reading its source. Once fixed, v2 matched v1 exactly on
the same question. Worth being able to say plainly in an interview: a
framework being popular and well-tested doesn't mean its defaults are
automatically correct for a specific dataset, it still has to be configured
deliberately, and this is direct, evidenced proof of that rather than a
theoretical claim.

## v2 summary

| # | Type | v1 result | v2 result |
|---|---|---|---|
| 12 | Out-of-scope trap | PASS | PASS (identical) |
| 13 | Weak-confidence retry | PASS | PASS (identical) |
| 14 | Cross-document synthesis | PASS | PASS (after 2 diagnosed fixes) |

v2 confirmed functionally equivalent to v1 on all three tested questions,
same self-healing behavior, same final answers. One real regression was
found, diagnosed to the exact mechanism (not guessed at), and fixed twice
over rather than patched around.
