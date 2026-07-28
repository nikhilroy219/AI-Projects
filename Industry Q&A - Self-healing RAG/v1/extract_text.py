"""
Step 1 of the RAG pipeline: pull raw text out of each source PDF.

What this does:
1. Looks in source_docs/ for every .pdf file
2. Extracts the text from each one using pypdf
3. Saves the extracted text as a matching .txt file in extracted_text/
4. Prints a summary table so we can sanity-check the extraction quality
   before moving on to chunking

Run with: python extract_text.py
"""

from pathlib import Path
from pypdf import PdfReader

SOURCE_DIR = Path("source_docs")
OUTPUT_DIR = Path("extracted_text")


def extract_pdf_text(pdf_path: Path) -> tuple[str, int]:
    """Returns (full_text, page_count) for a single PDF."""
    reader = PdfReader(pdf_path)
    page_count = len(reader.pages)

    pages_text = []
    for page in reader.pages:
        page_text = page.extract_text() or ""
        pages_text.append(page_text)

    full_text = "\n\n".join(pages_text)
    return full_text, page_count


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)

    pdf_files = sorted(SOURCE_DIR.glob("*.pdf"))
    if not pdf_files:
        print(f"No PDFs found in {SOURCE_DIR}/. Check the folder name and location.")
        return

    print(f"Found {len(pdf_files)} PDF(s) in {SOURCE_DIR}/\n")
    print(f"{'File':<40} {'Pages':>6} {'Characters':>12}")
    print("-" * 60)

    results = []
    for pdf_path in pdf_files:
        try:
            text, page_count = extract_pdf_text(pdf_path)
        except Exception as e:
            print(f"{pdf_path.name:<40} FAILED: {e}")
            continue

        char_count = len(text)
        results.append((pdf_path.name, page_count, char_count, text))

        print(f"{pdf_path.name:<40} {page_count:>6} {char_count:>12}")

        out_path = OUTPUT_DIR / (pdf_path.stem + ".txt")
        out_path.write_text(text, encoding="utf-8")

    print("\nSaved extracted text to extracted_text/\n")

    # Flag anything that looks like it extracted poorly
    # (very low characters per page usually means a scanned/image PDF)
    print("Quality check (chars per page, flag anything under 200):")
    for name, pages, chars, _ in results:
        chars_per_page = chars / pages if pages else 0
        flag = "  <-- LOW, may need OCR" if chars_per_page < 200 else ""
        print(f"  {name:<40} {chars_per_page:>8.0f} chars/page{flag}")

    print("\nPreview of first document:")
    if results:
        first_name, _, _, first_text = results[0]
        print(f"--- {first_name} (first 400 chars) ---")
        print(first_text[:400])


if __name__ == "__main__":
    main()
