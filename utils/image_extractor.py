"""
utils/image_extractor.py — Extract embedded images from a PDF using PyMuPDF.

Saves:
  - Individual embedded images  → {out_dir}/images/page_{n}_img_{i}.{ext}
  - Full page renders (150 DPI) → {out_dir}/page_images/{n}.png

Returns a manifest mapping (page_number, index) → relative file path so
the assembler can wire actual paths into 12_images.json.
"""
from __future__ import annotations

import logging
from pathlib import Path

import fitz  # PyMuPDF

log = logging.getLogger(__name__)

PAGE_RENDER_DPI = 150


def extract_images_from_pdf(
    pdf_path: str | Path,
    out_dir: str | Path,
) -> dict:
    """
    Extract all embedded raster images and render full pages.

    Returns:
        {
            "page_images": {page_num: "page_images/{n}.png", ...},
            "extracted":   {page_num: [{"index": i, "path": "images/...", "width": w, "height": h}, ...], ...},
            "total_extracted": int,
        }
    """
    pdf_path = Path(pdf_path)
    out_dir = Path(out_dir)

    images_dir = out_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    page_images_dir = out_dir / "page_images"
    page_images_dir.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(str(pdf_path))
    result: dict = {
        "page_images": {},
        "extracted": {},
        "total_extracted": 0,
    }

    for page_idx in range(len(doc)):
        page_num = page_idx + 1
        page = doc[page_idx]

        # Full page render
        pix = page.get_pixmap(dpi=PAGE_RENDER_DPI)
        page_img_rel = f"page_images/{page_num}.png"
        page_img_path = out_dir / page_img_rel
        if not page_img_path.exists():
            pix.save(str(page_img_path))
        result["page_images"][page_num] = page_img_rel

        # Embedded images
        page_extracted: list[dict] = []
        seen_xrefs: set[int] = set()

        for img_idx, img_info in enumerate(page.get_images(full=True)):
            xref = img_info[0]
            if xref in seen_xrefs:
                continue
            seen_xrefs.add(xref)

            try:
                base_image = doc.extract_image(xref)
            except Exception:
                continue

            if not base_image or not base_image.get("image"):
                continue

            ext = base_image.get("ext", "png")
            if ext == "jb2":
                ext = "png"
            w = base_image.get("width", 0)
            h = base_image.get("height", 0)

            # Skip tiny images (likely icons/bullets, < 20x20 px)
            if w < 20 and h < 20:
                continue

            seq = len(page_extracted)
            rel_path = f"images/page_{page_num}_img_{seq}.{ext}"
            abs_path = out_dir / rel_path

            with open(abs_path, "wb") as f:
                f.write(base_image["image"])

            page_extracted.append({
                "index": seq,
                "path": rel_path,
                "width": w,
                "height": h,
                "ext": ext,
            })
            result["total_extracted"] += 1

        result["extracted"][page_num] = page_extracted

    doc.close()

    log.info(
        "Extracted %d embedded images + %d page renders from %s",
        result["total_extracted"],
        len(result["page_images"]),
        pdf_path.name,
    )
    return result
