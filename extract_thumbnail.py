import sys
import fitz # PyMuPDF
import os

pdf_path = "static/uploads/HOWO avtomobil sotib olish biznes rejasi.pdf"
out_path = "static/img/catalog-howo.png"

try:
    doc = fitz.open(pdf_path)
    page = doc.load_page(0) # First page
    pix = page.get_pixmap(dpi=150)
    pix.save(out_path)
    print(f"Success. Thumbnail saved to {out_path}")
except Exception as e:
    print(f"Error: {e}")
