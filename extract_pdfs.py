from __future__ import annotations

import pdfplumber
from pathlib import Path


def extract_pdf_text(pdf_path: str) -> str:
    text_parts = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                text_parts.append(text)
    return "\n\n---PAGE---\n\n".join(text_parts)


def main():
    base = Path("E:/ТГ-агент")

    kalinka_dir = base / "Калинка МФ"
    opraim_dir = base / "Опрайм"

    for pdf_file in kalinka_dir.glob("*.pdf"):
        if (
            "ТО" in pdf_file.name
            or "krovat" in pdf_file.name
            or "divan" in pdf_file.name
            or "kresla" in pdf_file.name
        ):
            print(f"Processing: {pdf_file.name}")
            try:
                text = extract_pdf_text(str(pdf_file))
                output = pdf_file.with_suffix(".txt")
                output.write_text(text, encoding="utf-8")
                print(f"  -> saved to {output.name}")
            except Exception as e:
                print(f"  ERROR: {e}")

    for pdf_file in opraim_dir.glob("*.pdf"):
        print(f"Processing: {pdf_file.name}")
        try:
            text = extract_pdf_text(str(pdf_file))
            output = pdf_file.with_suffix(".txt")
            output.write_text(text, encoding="utf-8")
            print(f"  -> saved to {output.name}")
        except Exception as e:
            print(f"  ERROR: {e}")


if __name__ == "__main__":
    main()
