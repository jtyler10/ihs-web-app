import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import io
import streamlit as st

st.set_page_config(page_title="PDF Extraction — IHS", layout="centered")
st.title("PDF Text Extraction")
st.markdown(
    "Upload a scanned or mixed PDF to extract and clean the text for use in InDesign or Word. "
    "Image-only pages are automatically run through OCR."
)

uploaded = st.file_uploader("Choose a PDF file", type="pdf")

# Accept a PDF pre-loaded from the NextCloud browser
_nc_bytes = st.session_state.pop("_nc_pdf_bytes", None)
_nc_name  = st.session_state.pop("_nc_pdf_name", None)
if _nc_bytes and not uploaded:
    st.info(f"Using PDF from NextCloud: **{_nc_name}**")

if uploaded or _nc_bytes:
    try:
        import fitz          # PyMuPDF
        from PIL import Image
        import pytesseract
    except ImportError as e:
        st.error(f"Missing dependency: {e}. The app may still be deploying — try again in a minute.")
        st.stop()

    pdf_bytes = _nc_bytes if _nc_bytes else uploaded.read()
    pdf_name  = _nc_name  if _nc_bytes else uploaded.name
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    total_pages = len(doc)

    pages_with_text = sum(
        1 for i in range(total_pages) if len(doc[i].get_text().strip()) > 20
    )
    image_only = total_pages - pages_with_text

    st.info(
        f"**{total_pages}** pages — "
        f"**{pages_with_text}** with embedded text, "
        f"**{image_only}** image-only (will be OCR'd)."
    )

    if image_only > 0:
        st.warning(
            f"OCR will run on {image_only} page(s). "
            "This may take a minute for longer documents."
        )

    # ── Extract and clean ─────────────────────────────────────────────
    def clean_page_text(lines):
        """Join broken lines into paragraphs, strip OCR garbage."""
        cleaned = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            alpha = sum(c.isalpha() or c.isspace() or c in "',.-;:!?" for c in line)
            if len(line) > 4 and alpha / len(line) < 0.4:
                continue
            cleaned.append(line)

        paragraphs = []
        buffer = ""
        for line in cleaned:
            if buffer:
                if buffer.endswith("-"):
                    buffer = buffer[:-1] + line
                else:
                    buffer = buffer + " " + line
            else:
                buffer = line
            if line and line[-1] in '.!?:"\'':
                paragraphs.append(buffer.strip())
                buffer = ""
        if buffer:
            paragraphs.append(buffer.strip())

        return "\n\n".join(paragraphs)


    def ocr_page(page):
        """Render a PDF page to an image and run Tesseract OCR on it."""
        mat = fitz.Matrix(2.0, 2.0)  # 2x scale for better accuracy
        pix = page.get_pixmap(matrix=mat, colorspace=fitz.csGRAY)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        return pytesseract.image_to_string(img, config="--psm 1")


    with st.spinner("Extracting text… (OCR pages may take a moment)"):
        progress = st.progress(0)
        pages_output = []

        for i in range(total_pages):
            progress.progress((i + 1) / total_pages)
            page = doc[i]
            raw = page.get_text().strip()

            if len(raw) > 20:
                # Embedded text — clean and join lines
                text = clean_page_text(raw.splitlines())
            else:
                # Image-only — run OCR
                try:
                    ocr_raw = ocr_page(page)
                    text = clean_page_text(ocr_raw.splitlines())
                    if not text.strip():
                        text = f"[PAGE {i+1} — OCR RETURNED NO TEXT]"
                except Exception as e:
                    text = f"[PAGE {i+1} — OCR ERROR: {e}]"

            if text:
                pages_output.append(text)

        doc.close()
        progress.empty()

    cleaned_text = "\n\n".join(pages_output)

    # ── Preview ───────────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("Preview (first 3,000 characters)")
    st.text_area("Extracted text", cleaned_text[:3000], height=400)

    # ── Download ──────────────────────────────────────────────────────
    base_name = os.path.splitext(pdf_name)[0]
    out_filename = f"{base_name}_extracted.txt"

    st.download_button(
        label="Download cleaned text (.txt)",
        data=cleaned_text.encode("utf-8"),
        file_name=out_filename,
        mime="text/plain",
        type="primary",
        use_container_width=True,
    )
