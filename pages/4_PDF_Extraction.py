import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import io
import streamlit as st

st.set_page_config(page_title="PDF Extraction — IHS", layout="centered")
st.title("PDF Text Extraction")
st.markdown(
    "Upload a scanned or mixed PDF to extract and clean the text for use in InDesign or Word."
)

uploaded = st.file_uploader("Choose a PDF file", type="pdf")

if uploaded:
    with st.spinner("Extracting text…"):
        try:
            import fitz  # PyMuPDF

            pdf_bytes = uploaded.read()
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")

            total_pages = len(doc)
            pages_with_text = sum(
                1 for i in range(total_pages) if len(doc[i].get_text().strip()) > 20
            )

            st.info(
                f"**{total_pages}** pages — "
                f"**{pages_with_text}** with extractable text, "
                f"**{total_pages - pages_with_text}** image-only."
            )

            # ── Extract and clean ─────────────────────────────────────
            def extract_and_clean(doc):
                pages_text = []
                for i in range(len(doc)):
                    raw = doc[i].get_text().strip()
                    if not raw:
                        pages_text.append(f"[PAGE {i+1} — IMAGE ONLY, NO TEXT]\n")
                        continue

                    lines = raw.splitlines()
                    cleaned = []
                    for line in lines:
                        line = line.strip()
                        if not line:
                            continue
                        # Drop lines that are mostly non-alpha (OCR garbage/stamps)
                        alpha = sum(c.isalpha() or c.isspace() or c in "',.-;:!?" for c in line)
                        if len(line) > 4 and alpha / len(line) < 0.4:
                            continue
                        cleaned.append(line)

                    if not cleaned:
                        continue

                    # Join broken lines into paragraphs
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

                    pages_text.append("\n\n".join(paragraphs))

                return "\n\n".join(pages_text)

            cleaned_text = extract_and_clean(doc)
            doc.close()

            # ── Preview ───────────────────────────────────────────────
            st.markdown("---")
            st.subheader("Preview (first 3,000 characters)")
            st.text_area("Extracted text", cleaned_text[:3000], height=400)

            # ── Download ──────────────────────────────────────────────
            base_name = os.path.splitext(uploaded.name)[0]
            out_filename = f"{base_name}_extracted.txt"

            st.download_button(
                label="Download cleaned text (.txt)",
                data=cleaned_text.encode("utf-8"),
                file_name=out_filename,
                mime="text/plain",
                type="primary",
                use_container_width=True,
            )

        except ImportError:
            st.error(
                "PyMuPDF is not installed. Add `pymupdf` to requirements.txt and redeploy."
            )
        except Exception as e:
            st.error(f"Extraction error: {e}")
