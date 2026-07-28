"""
One-off diagnostic, not part of the pipeline: searches v2's database
directly for the offshore wind capacity figures, to see exactly how that
text got split into chunks. This replaces guessing with actually looking.

Run with: python inspect_chunks.py
"""

import chromadb

DB_DIR = "chroma_db"
COLLECTION_NAME = "energy_docs"
SOURCE_FILTER = "2_EU_Offshore_Strategy_2020"
SEARCH_TERMS = ["300 GW", "300GW", "nearly 30 times"]

client = chromadb.PersistentClient(path=DB_DIR)
collection = client.get_collection(COLLECTION_NAME)

results = collection.get(where={"source": SOURCE_FILTER})
ids = results["ids"]
docs = results["documents"]

print(f"{SOURCE_FILTER} has {len(docs)} chunks in this database.\n")

found_any = False
for chunk_id, text in zip(ids, docs):
    for term in SEARCH_TERMS:
        if term.lower() in text.lower():
            found_any = True
            print(f"--- {chunk_id} (contains '{term}') ---")
            print(text)
            print()
            break

if not found_any:
    print("None of the search terms appear whole in any single chunk.")
    print("Showing every chunk that contains the word 'offshore' and a number near 300, for manual inspection:\n")
    import re
    for chunk_id, text in zip(ids, docs):
        if "offshore" in text.lower() and re.search(r"\b(2[5-9]\d|30\d)\b", text):
            print(f"--- {chunk_id} ---")
            print(text)
            print()
