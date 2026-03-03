"""
utils/image_extractor.py — Extract embedded images from a PDF using PyMuPDF.

Saves:
  - Individual embedded raster images → {out_dir}/images/page_{n}_img_{i}.{ext}
  - Vector drawing clusters (graphs)  → {out_dir}/images/page_{n}_graph_{i}.png  (300 DPI)
  - Full page renders (150 DPI)       → {out_dir}/page_images/{n}.png

Returns a manifest mapping (page_number, index) → relative file path so
the assembler can wire actual paths into 12_images.json.
"""
from __future__ import annotations

import logging
from pathlib import Path

import fitz  # PyMuPDF

log = logging.getLogger(__name__)

# Full-page reference renders (used as fallback thumbnails only)
PAGE_RENDER_DPI = 150
# Graph/coordinate-plane crops — print-ready quality (≥ 300 DPI)
GRAPH_CROP_DPI = 300

# Minimum drawing-cluster dimensions (PDF points, 1pt = 1/72 inch)
# A coordinate plane is typically ≥ 1.5 inch square → ~108 pt
_MIN_GRAPH_PT = 80
# Minimum number of drawing paths that must contribute to a cluster
_MIN_GRAPH_PATHS = 4
# Proximity margin for clustering adjacent drawing paths (pt)
_CLUSTER_MARGIN = 15
# Filled-rectangle area (pt²) above which a path counts as a "large fill"
# (background boxes, banners). 3600 pt² ≈ 1 in² at 72 dpi.
_LARGE_FILL_AREA = 3600
# Maximum number of large fills a cluster may contain and still be considered
# a graph.  Decorative section headers / callout boxes routinely exceed this.
_MAX_LARGE_FILLS = 1


def extract_images_from_pdf(
    pdf_path: str | Path,
    out_dir: str | Path,
) -> dict:
    """
    Extract all embedded raster images, detect vector graph regions, and render
    full pages.

    Returns:
        {
            "page_images":    {page_num: "page_images/{n}.png", ...},
            "extracted":      {page_num: [{"index": i, "path": "images/...",
                                           "width": w, "height": h}, ...], ...},
            "graph_regions":  {page_num: [{"index": i, "path": "images/...",
                                           "width": w, "height": h}, ...], ...},
            "total_extracted": int,
            "total_graphs":    int,
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
        "graph_regions": {},
        "total_extracted": 0,
        "total_graphs": 0,
    }

    for page_idx in range(len(doc)):
        page_num = page_idx + 1
        page = doc[page_idx]

        # ── Full page render ───────────────────────────────────────────────
        pix = page.get_pixmap(dpi=PAGE_RENDER_DPI)
        page_img_rel = f"page_images/{page_num}.png"
        page_img_path = out_dir / page_img_rel
        if not page_img_path.exists():
            pix.save(str(page_img_path))
        result["page_images"][page_num] = page_img_rel

        # ── Embedded raster images ─────────────────────────────────────────
        page_extracted: list[dict] = []
        seen_xrefs: set[int] = set()

        for img_info in page.get_images(full=True):
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

            # Skip tiny images (likely icons/bullets, < 20×20 px)
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

        # ── Vector drawing regions (coordinate planes / graphs) ────────────
        graph_crops = _find_graph_regions(page, out_dir, page_num,
                                          page.get_drawings())
        result["graph_regions"][page_num] = graph_crops
        result["total_graphs"] += len(graph_crops)

    doc.close()

    log.info(
        "Extracted %d raster images + %d graph regions + %d page renders from %s",
        result["total_extracted"],
        result["total_graphs"],
        len(result["page_images"]),
        pdf_path.name,
    )
    return result


# ── Vector graph region detection ─────────────────────────────────────────────

def _find_graph_regions(
    page: fitz.Page,
    out_dir: Path,
    page_num: int,
    drawings: list[dict] | None = None,
) -> list[dict]:
    """
    Detect coordinate-plane / graph regions on a page via vector drawing analysis.

    Clusters nearby drawing paths, filters by minimum size, path count, and
    large-fill count (to skip decorative banners, callout boxes, etc.), then
    renders each qualifying cluster as a PNG crop.

    Returns a list of dicts sorted by visual position (top → bottom, left → right):
        [{"index": int, "path": str, "width": int, "height": int, "ext": "png"}, ...]
    """
    if drawings is None:
        drawings = page.get_drawings()
    if not drawings:
        return []

    # Collect bounding rects of non-trivial individual paths
    path_rects: list[fitz.Rect] = []
    for d in drawings:
        r = d.get("rect")
        if r and r.width > 5 and r.height > 5:
            path_rects.append(fitz.Rect(r))

    if len(path_rects) < _MIN_GRAPH_PATHS:
        return []

    # Pre-compute large-fill rects for cheap cluster-level checks
    large_fill_rects: list[fitz.Rect] = [
        fitz.Rect(d["rect"])
        for d in drawings
        if d.get("fill") is not None
        and d.get("rect") is not None
        and fitz.Rect(d["rect"]).width * fitz.Rect(d["rect"]).height >= _LARGE_FILL_AREA
    ]

    clusters = _cluster_with_counts(path_rects, margin=_CLUSTER_MARGIN)

    page_w = page.rect.width
    page_h = page.rect.height
    # Use print-quality DPI for graph crops so they are usable in print layouts
    mat = fitz.Matrix(GRAPH_CROP_DPI / 72, GRAPH_CROP_DPI / 72)

    results: list[dict] = []

    for cluster_rect, path_count, cluster_paths in clusters:
        # Must be large enough
        if cluster_rect.width < _MIN_GRAPH_PT or cluster_rect.height < _MIN_GRAPH_PT:
            continue
        # Must have enough contributing paths (rules out single borders)
        if path_count < _MIN_GRAPH_PATHS:
            continue
        # Must not cover the entire page (avoid full-page captures)
        if cluster_rect.width > page_w * 0.95 and cluster_rect.height > page_h * 0.95:
            continue

        # Decorative elements (banners, callout boxes) contain multiple large
        # filled rectangles.  Real graphs have at most one (the plot-area bg).
        large_fills = sum(
            1 for r in large_fill_rects
            if cluster_rect.contains(r) or cluster_rect.intersects(r)
        )
        if large_fills > _MAX_LARGE_FILLS:
            log.debug(
                "Page %d: skipping %dx%d pt cluster — %d large fills (decorative)",
                page_num, int(cluster_rect.width), int(cluster_rect.height),
                large_fills,
            )
            continue

        # Split merged side-by-side or stacked graphs into individual regions
        sub_rects = _split_cluster_by_gaps(cluster_rect, cluster_paths)

        # Recursively try to split each piece (catches cases where a narrower
        # gap wasn't visible until after the first split reduced the bounding box)
        if len(sub_rects) > 1:
            refined: list[fitz.Rect] = []
            for sr in sub_rects:
                sr_paths = [
                    r for r in cluster_paths
                    if r.x0 < sr.x1 and r.x1 > sr.x0
                    and r.y0 < sr.y1 and r.y1 > sr.y0
                ]
                refined.extend(_split_cluster_by_gaps(sr, sr_paths))
            sub_rects = refined

        for sub_rect in sub_rects:
            clip = page.rect & sub_rect
            if clip.is_empty or clip.width < 50 or clip.height < 50:
                continue

            pix = page.get_pixmap(matrix=mat, clip=clip)
            seq = len(results)
            rel_path = f"images/page_{page_num}_graph_{seq}.png"
            abs_path = out_dir / rel_path
            pix.save(str(abs_path))

            results.append({
                "index": seq,
                "path": rel_path,
                "width": pix.width,
                "height": pix.height,
                "ext": "png",
                "source": "vector_drawing",
                "_y": clip.y0,
                "_x": clip.x0,
            })
            log.debug(
                "Page %d: graph region %dx%d pt at (%.0f, %.0f) — %d paths, %d large fills",
                page_num, int(sub_rect.width), int(sub_rect.height),
                clip.x0, clip.y0, path_count, large_fills,
            )

    # Sort top-to-bottom, left-to-right to match Gemini's reading order
    results.sort(key=lambda r: (r.pop("_y"), r.pop("_x")))
    # Re-index after sort
    for i, r in enumerate(results):
        r["index"] = i

    return results


def _cluster_with_counts(
    rects: list[fitz.Rect],
    margin: int = 15,
) -> list[tuple[fitz.Rect, int, list[fitz.Rect]]]:
    """
    Iteratively merge rects that are within *margin* points of each other.

    Returns a list of (union_rect, contributing_path_count, path_rects) tuples.
    path_rects is the list of original rects that merged into this cluster —
    used downstream for gap-based splitting.
    """
    # Each cluster starts as (rect, count=1, [rect])
    clusters: list[tuple[fitz.Rect, int, list[fitz.Rect]]] = [
        (fitz.Rect(r), 1, [fitz.Rect(r)]) for r in rects
    ]

    changed = True
    while changed:
        changed = False
        new_clusters: list[tuple[fitz.Rect, int, list[fitz.Rect]]] = []
        used = [False] * len(clusters)

        for i, (c_rect, c_cnt, c_paths) in enumerate(clusters):
            if used[i]:
                continue
            merged_rect  = fitz.Rect(c_rect)
            merged_cnt   = c_cnt
            merged_paths = list(c_paths)

            for j in range(i + 1, len(clusters)):
                if used[j]:
                    continue
                j_rect, j_cnt, j_paths = clusters[j]
                expanded = fitz.Rect(
                    merged_rect.x0 - margin, merged_rect.y0 - margin,
                    merged_rect.x1 + margin, merged_rect.y1 + margin,
                )
                if expanded.intersects(j_rect):
                    merged_rect   = merged_rect | j_rect
                    merged_cnt   += j_cnt
                    merged_paths += j_paths
                    used[j]       = True
                    changed       = True

            used[i] = True
            new_clusters.append((merged_rect, merged_cnt, merged_paths))

        clusters = new_clusters

    return clusters


def _split_cluster_by_gaps(
    cluster_rect: fitz.Rect,
    path_rects: list[fitz.Rect],
    min_gap_pt: float = 3.0,
) -> list[fitz.Rect]:
    """
    Split a merged cluster into individual sub-regions by finding empty strips.

    Works on both axes:
    - Horizontally (columns) when the cluster is wider than 1.5× its height
      → separates side-by-side graphs (e.g. three coordinate planes in a row)
    - Vertically (rows) when the cluster is taller than 1.5× its width
      → separates stacked graphs

    If no gap ≥ *min_gap_pt* is found, returns [cluster_rect] unchanged.
    """
    splits: list[fitz.Rect] = []

    def _gaps_on_axis(lo: float, hi: float, intervals: list[tuple[float, float]]) -> list[float]:
        """Return midpoints of gaps ≥ min_gap_pt between merged intervals."""
        if not intervals:
            return []
        ivs = sorted(intervals, key=lambda iv: iv[0])
        # Merge overlapping intervals
        merged: list[list[float]] = [list(ivs[0])]
        for a, b in ivs[1:]:
            if a <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], b)
            else:
                merged.append([a, b])
        # Find gaps between merged intervals
        cuts: list[float] = []
        for k in range(len(merged) - 1):
            gap_start = merged[k][1]
            gap_end   = merged[k + 1][0]
            if gap_end - gap_start >= min_gap_pt:
                cuts.append((gap_start + gap_end) / 2.0)
        return cuts

    # ── Try horizontal split (side-by-side graphs) ────────────────────────
    if cluster_rect.width >= 1.5 * cluster_rect.height:
        x_ivs = [(r.x0, r.x1) for r in path_rects]
        cuts  = _gaps_on_axis(cluster_rect.x0, cluster_rect.x1, x_ivs)
        if cuts:
            x_edges = [cluster_rect.x0] + cuts + [cluster_rect.x1]
            for k in range(len(x_edges) - 1):
                sub = fitz.Rect(x_edges[k], cluster_rect.y0,
                                x_edges[k + 1], cluster_rect.y1)
                if sub.width >= _MIN_GRAPH_PT:
                    splits.append(sub)
            if splits:
                return splits

    # ── Try vertical split (stacked graphs) ───────────────────────────────
    if cluster_rect.height >= 1.5 * cluster_rect.width:
        y_ivs = [(r.y0, r.y1) for r in path_rects]
        cuts  = _gaps_on_axis(cluster_rect.y0, cluster_rect.y1, y_ivs)
        if cuts:
            y_edges = [cluster_rect.y0] + cuts + [cluster_rect.y1]
            for k in range(len(y_edges) - 1):
                sub = fitz.Rect(cluster_rect.x0, y_edges[k],
                                cluster_rect.x1, y_edges[k + 1])
                if sub.height >= _MIN_GRAPH_PT:
                    splits.append(sub)
            if splits:
                return splits

    return [cluster_rect]
