"""
v2, ingestion step: the LangChain rebuild of v1's extract_text.py +
chunk_documents.py + generate_embeddings.py + build_vector_db.py, combined
into one script.

Same inputs, same models, same outputs as v1, just built with LangChain's
pre-built classes instead of hand-written functions:
- PyPDFLoader          instead of manual pypdf page-by-page extraction
- RecursiveCharacterTextSplitter   instead of our hand-written sliding window
- HuggingFaceEmbeddings            instead of calling SentenceTransformer directly
- Chroma.from_documents()          combines embedding + storage into one call

Reads the same 7 PDFs already sitting in v1/source_docs, no need to
duplicate them. Writes to its own chroma_db here in v2/, kept separate from
v1's database so both versions are fully independent and this script
provably rebuilds everything itself rather than reusing v1's work.

Run with: python build_index.py
"""

from pathlib import Path
import re

import chromadb
from langchain_chroma import Chroma
from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

SOURCE_DIR = Path("../v1/source_docs")
DB_DIR = "chroma_db"
COLLECTION_NAME = "energy_docs"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150


def clean_pdf_text(text: str) -> str:
    """Normalize raw PDF-extracted text before chunking.

    PDF extraction leaves a line break wherever a line visually wrapped on
    the page, not wherever a sentence or paragraph actually ended. Left
    alone, two problems follow: the text splitter treats every one of
    those line breaks as a preferred place to cut (its separator list
    tries "\\n" before " "), fragmenting sentences that were never meant
    to be split, and the embedding model later gets a differently-shaped
    input than what informed the chunk boundaries. Cleaning this before
    splitting, standard practice for PDF-based RAG, fixes both at once.
    """
    # Collapse 3+ line breaks down to a standard paragraph break
    text = re.sub(r"\n{3,}", "\n\n", text)
    # A single line break (not part of a \n\n pair) is a mid-paragraph
    # line-wrap, not a real paragraph break, flatten it to a space
    text = re.sub(r"(?<!\n)\n(?!\n)", " ", text)
    # Collapse repeated spaces/tabs left behind by the above
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def main():
    pdf_files = sorted(SOURCE_DIR.glob("*.pdf"))
    if not pdf_files:
        print(f"No PDFs found in {SOURCE_DIR}/. Check the path, v2 reuses v1's source_docs.")
        return

    print(f"Found {len(pdf_files)} PDF(s)\n")

    # PyPDFLoader gives one Document per page, and the splitter never merges
    # content across separate Document objects, so a chunk could never span
    # a page break if we split the pages as-is. We merge each PDF's pages
    # into one continuous Document first, matching v1's approach of
    # chunking over the full document text rather than per-page, then
    # clean the merged text before splitting.
    full_documents = []
    for pdf_path in pdf_files:
        loader = PyPDFLoader(str(pdf_path))
        pages = loader.load()
        raw_text = "\n\n".join(page.page_content for page in pages)
        cleaned_text = clean_pdf_text(raw_text)
        full_documents.append(Document(page_content=cleaned_text, metadata={"source": pdf_path.stem}))
        print(f"  {pdf_path.name:<40} {len(pages):>4} pages, {len(cleaned_text):>8} chars (cleaned)")

    print(f"\nLoaded {len(full_documents)} documents (pages merged and cleaned per source)")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )
    chunks = splitter.split_documents(full_documents)
    print(f"Split into {len(chunks)} chunks (chunk_size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP})")

    print(f"\nLoading embedding model: {EMBEDDING_MODEL} (same model as v1)...")
    embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)

    # Start fresh every run, avoids duplicate chunks stacking up if this
    # script gets run more than once against the same database folder.
    print("Clearing any existing collection to avoid duplicate entries on re-run...")
    client = chromadb.PersistentClient(path=DB_DIR)
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass

    print("Embedding and storing in Chroma (one call does both steps)...")
    Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        collection_name=COLLECTION_NAME,
        persist_directory=DB_DIR,
    )

    print(f"\nDone. {len(chunks)} chunks stored in {DB_DIR}/")


if __name__ == "__main__":
    main()
