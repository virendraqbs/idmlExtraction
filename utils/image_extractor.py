"""
utils/image_extractor.py — Extract print-ready images from a PDF using PyMuPDF.

Two extraction modes:
  1. Embedded raster images — cropped at 300 DPI with noise filtering
  2. Vector graphic clusters — detected via get_drawings(), merged, cropped

After extraction, images are spatially matched to Gemini-described image metadata
(alt_text, description, image_type, etc.) using position-based proximity.

Saves:
  - Print-ready images    → {out_dir}/images/page_{n}_img_{seq}.png
  - Full page renders     → {out_dir}/page_images/{n}.png

Returns a manifest keyed by pdf_page_index for the assembler.
"""
from __future__ import annotations

import logging
from pathlib import Path

import fitz  # PyMuPDF

log = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────
CROP_DPI = 300
PAGE_RENDER_DPI = 150
MIN_RASTER_DIM = 50
MIN_RASTER_BBOX = 20
MIN_VECTOR_AREA = 3600
MIN_VECTOR_DIM = 50
CLUSTER_GAP = 20
MAX_FULL_PAGE_RATIO = 0.9

POSITION_CENTRES: dict[str, tuple[float, float]] = {
    "TOP_LEFT": (0.17, 0.17), "TOP_CENTER": (0.50, 0.17), "TOP_RIGHT": (0.83, 0.17),
    "MIDDLE_LEFT": (0.17, 0.50), "MIDDLE_CENTER": (0.50, 0.50), "MIDDLE_RIGHT": (0.83, 0.50),
    "BOTTOM_LEFT": (0.17, 0.83), "BOTTOM_CENTER": (0.50, 0.83), "BOTTOM_RIGHT": (0.83, 0.83),
    "LEFT_SIDEBAR": (0.08, 0.50), "RIGHT_SIDEBAR": (0.92, 0.50), "FULL_WIDTH": (0.50, 0.50),
}


# ── Vector drawing clustering ─────────────────────────────────────────────────

def _cluster_drawings(drawings: list, page_rect: fitz.Rect) -> list[fitz.Rect]:
    rects: list[fitz.Rect] = []
    for d in drawings:
        r = fitz.Rect(d["rect"])
        if r.is_empty or r.is_infinite or (r.width < 8 and r.height < 8):
            continue
        rects.append(r)
    if not rects:
        return []

    clusters = [rects[0]]
    for r in rects[1:]:
        merged = False
        for i, c in enumerate(clusters):
            expanded = c + fitz.Rect(-CLUSTER_GAP, -CLUSTER_GAP, CLUSTER_GAP, CLUSTER_GAP)
            if expanded.intersects(r):
                clusters[i] = c | r
                merged = True
                break
        if not merged:
            clusters.append(r)

    changed = True
    while changed:
        changed = False
        new_clusters: list[fitz.Rect] = []
        used: set[int] = set()
        for i, c1 in enumerate(clusters):
            if i in used:
                continue
            merged_rect = c1
            for j, c2 in enumerate(clusters):
                if j <= i or j in used:
                    continue
                expanded = merged_rect + fitz.Rect(-CLUSTER_GAP, -CLUSTER_GAP, CLUSTER_GAP, CLUSTER_GAP)
                if expanded.intersects(c2):
                    merged_rect = merged_rect | c2
                    used.add(j)
                    changed = True
            new_clusters.append(merged_rect)
            used.add(i)
        clusters = new_clusters

    return [c for c in clusters if c.width * c.height > MIN_VECTOR_AREA]


def _overlaps_any(rect: fitz.Rect, existing: list[fitz.Rect], threshold: float = 0.5) -> bool:
    for ex in existing:
        intersection = rect & ex
        if intersection.is_empty:
            continue
        inter_area = intersection.width * intersection.height
        rect_area = rect.width * rect.height
        if rect_area > 0 and inter_area / rect_area > threshold:
            return True
    return False


def _is_header_footer(rect: fitz.Rect, page_rect: fitz.Rect) -> bool:
    pw, ph = page_rect.width, page_rect.height
    if rect.height > ph * 0.15:
        return False
    if rect.y0 < ph * 0.10 or rect.y1 > ph * 0.90:
        if rect.width > pw * 0.6:
            return True
    return False


# ── Position-based matching ───────────────────────────────────────────────────

_LARGE_TYPES = {"TECHNICAL_ART", "INSTRUCTIONAL", "DIAGRAM", "PHOTOGRAPH"}
_SMALL_TYPES = {"ICON", "DECORATIVE"}
LARGE_IMAGE_AREA = 400 * 400


def _distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


def _match_cost(
    ext_img: dict,
    gimg: dict,
    pos_frac: tuple[float, float],
    cx: float,
    cy: float,
) -> float:
    """Compute matching cost combining position distance + type affinity."""
    dist = _distance((cx, cy), pos_frac)
    img_area = ext_img["width"] * ext_img["height"]
    img_type = (gimg.get("image_type") or "").upper()

    penalty = 0.0
    if img_area > LARGE_IMAGE_AREA and img_type in _SMALL_TYPES:
        penalty += 0.3
    if img_area < LARGE_IMAGE_AREA and img_type in _LARGE_TYPES:
        penalty += 0.15

    return dist + penalty


def _match_to_gemini(
    extracted: list[dict],
    gemini_images: list[dict],
    page_width: float,
    page_height: float,
) -> list[dict]:
    """Match extracted images to Gemini metadata using optimal assignment."""
    gemini_with_pos: list[tuple[int, tuple[float, float]]] = []
    for gi, gimg in enumerate(gemini_images):
        pos_str = (gimg.get("position") or "").upper()
        if pos_str in POSITION_CENTRES:
            gemini_with_pos.append((gi, POSITION_CENTRES[pos_str]))

    if not extracted or not gemini_with_pos:
        for ext_img in extracted:
            ext_img["matched_gemini"] = None
        return extracted

    ext_centres: list[tuple[float, float]] = []
    for ext_img in extracted:
        bbox = ext_img["bbox"]
        cx = max(0.0, min(1.0, (bbox[0] + bbox[2]) / 2 / page_width))
        cy = max(0.0, min(1.0, (bbox[1] + bbox[3]) / 2 / page_height))
        ext_centres.append((cx, cy))

    n_ext = len(extracted)
    n_gem = len(gemini_with_pos)
    cost = [[999.0] * n_gem for _ in range(n_ext)]
    for ei in range(n_ext):
        for gj, (gi, pos_frac) in enumerate(gemini_with_pos):
            cost[ei][gj] = _match_cost(
                extracted[ei], gemini_images[gi], pos_frac,
                ext_centres[ei][0], ext_centres[ei][1],
            )

    assignment: dict[int, int] = {}
    used_ext: set[int] = set()
    used_gem: set[int] = set()

    pairs = []
    for ei in range(n_ext):
        for gj in range(n_gem):
            pairs.append((cost[ei][gj], ei, gj))
    pairs.sort()

    for c, ei, gj in pairs:
        if ei in used_ext or gj in used_gem:
            continue
        if c > 0.8:
            break
        assignment[ei] = gj
        used_ext.add(ei)
        used_gem.add(gj)

    for ei, ext_img in enumerate(extracted):
        if ei in assignment:
            gi = gemini_with_pos[assignment[ei]][0]
            ext_img["matched_gemini"] = gemini_images[gi]
        else:
            ext_img["matched_gemini"] = None

    return extracted


# ── Main extraction ───────────────────────────────────────────────────────────

def extract_images_from_pdf(
    pdf_path: str | Path,
    out_dir: str | Path,
    gemini_pages: list[dict] | None = None,
) -> dict:
    """
    Extract all meaningful images and render full pages.

    Args:
        pdf_path:     Path to the PDF file
        out_dir:      Output directory
        gemini_pages: Raw per-page dicts from Gemini (for alt-text mapping).
                      Each page dict should have _pdf_page_index and images[].

    Returns:
        {
            "page_images": {page_num: "page_images/{n}.png", ...},
            "extracted":   {page_num: [{"index": i, "path": ..., "width": w, "height": h, ...}, ...], ...},
            "total_extracted": int,
        }
    """
    pdf_path = Path(pdf_path)
    out_dir = Path(out_dir)

    images_dir = out_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    page_images_dir = out_dir / "page_images"
    page_images_dir.mkdir(parents=True, exist_ok=True)

    gemini_by_page: dict[int, list[dict]] = {}
    if gemini_pages:
        for p in gemini_pages:
            idx = p.get("_pdf_page_index") or p.get("page_number")
            if idx is not None:
                gemini_by_page[idx] = p.get("images") or []

    doc = fitz.open(str(pdf_path))
    result: dict = {"page_images": {}, "extracted": {}, "total_extracted": 0}

    crop_mat = fitz.Matrix(CROP_DPI / 72, CROP_DPI / 72)

    for page_idx in range(len(doc)):
        page_num = page_idx + 1
        page = doc[page_idx]
        pw, ph = page.rect.width, page.rect.height
        page_area = pw * ph

        # Full page render
        pix = page.get_pixmap(dpi=PAGE_RENDER_DPI)
        page_img_rel = f"page_images/{page_num}.png"
        page_img_path = out_dir / page_img_rel
        if not page_img_path.exists():
            pix.save(str(page_img_path))
        result["page_images"][page_num] = page_img_rel

        extracted_rects: list[fitz.Rect] = []
        page_extracted: list[dict] = []
        seq = 0

        # ── Raster images ─────────────────────────────────────────────────
        image_infos = page.get_image_info(xrefs=True)
        for i, info in enumerate(image_infos):
            bbox = fitz.Rect(info["bbox"])
            xref = info.get("xref", 0)
            w, h = info.get("width", 0), info.get("height", 0)

            if w < MIN_RASTER_DIM and h < MIN_RASTER_DIM:
                continue
            if bbox.width < MIN_RASTER_BBOX or bbox.height < MIN_RASTER_BBOX:
                continue
            if _is_header_footer(bbox, page.rect):
                continue

            clipped = bbox & page.rect
            if clipped.is_empty or clipped.width < 2 or clipped.height < 2:
                continue

            try:
                pix = page.get_pixmap(matrix=crop_mat, clip=clipped)
                if pix.width < 2 or pix.height < 2:
                    continue
            except Exception:
                continue

            seq += 1
            rel_path = f"images/page_{page_num}_img_{seq}.png"
            pix.save(str(out_dir / rel_path))

            entry = {
                "index": seq - 1,
                "path": rel_path,
                "width": pix.width,
                "height": pix.height,
                "ext": "png",
                "source": "raster",
                "bbox": (bbox.x0, bbox.y0, bbox.x1, bbox.y1),
            }
            page_extracted.append(entry)
            extracted_rects.append(bbox)

        # ── Vector clusters ───────────────────────────────────────────────
        drawings = page.get_drawings()
        if drawings:
            clusters = _cluster_drawings(drawings, page.rect)
            for cluster_rect in clusters:
                if _overlaps_any(cluster_rect, extracted_rects):
                    continue
                cw, ch = cluster_rect.width, cluster_rect.height
                if cw < MIN_VECTOR_DIM or ch < MIN_VECTOR_DIM:
                    continue
                if (cw * ch) / page_area > MAX_FULL_PAGE_RATIO:
                    continue
                if _is_header_footer(cluster_rect, page.rect):
                    continue

                padded = cluster_rect + fitz.Rect(-4, -4, 4, 4)
                padded &= page.rect
                if padded.is_empty or padded.width < 2 or padded.height < 2:
                    continue

                try:
                    pix = page.get_pixmap(matrix=crop_mat, clip=padded)
                    if pix.width < 2 or pix.height < 2:
                        continue
                except Exception:
                    continue

                seq += 1
                rel_path = f"images/page_{page_num}_img_{seq}.png"
                pix.save(str(out_dir / rel_path))

                entry = {
                    "index": seq - 1,
                    "path": rel_path,
                    "width": pix.width,
                    "height": pix.height,
                    "ext": "png",
                    "source": "vector",
                    "bbox": (cluster_rect.x0, cluster_rect.y0,
                             cluster_rect.x1, cluster_rect.y1),
                }
                page_extracted.append(entry)
                extracted_rects.append(cluster_rect)

        # ── Match to Gemini alt-text ──────────────────────────────────────
        gemini_imgs = gemini_by_page.get(page_num, [])
        non_decorative = [g for g in gemini_imgs if g.get("image_type") != "DECORATIVE"]
        _match_to_gemini(page_extracted, non_decorative, pw, ph)

        result["extracted"][page_num] = page_extracted
        result["total_extracted"] += len(page_extracted)

    doc.close()

    log.info(
        "Extracted %d images (raster+vector) + %d page renders from %s",
        result["total_extracted"],
        len(result["page_images"]),
        pdf_path.name,
    )
    return result
