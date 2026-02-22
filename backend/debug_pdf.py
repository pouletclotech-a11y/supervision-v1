import pdfplumber
import sys

path = '/app/data/archive/2026/02/06/2026-02-06-06-YPSILON_HISTO.pdf'
with pdfplumber.open(path) as pdf:
    text = pdf.pages[0].extract_text()
    lines = text.split('\n')
    for i, line in enumerate(lines[:30]):
        print(f"[{i:02d}] {line}")
