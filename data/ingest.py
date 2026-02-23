"""data/ingest.py — Pipeline de ingesta: raw → chunks JSONL

Lee documentos legales de data/raw/ (HTML + PDF), extrae texto,
genera chunks estructurados por unidades legales, y produce
los JSONL finales en data/processed/chunks_legal/.

Uso:
    python data/ingest.py
"""

from pathlib import Path
import json
import re
import hashlib

from bs4 import BeautifulSoup
from pypdf import PdfReader

# ── Rutas ───────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"
OUT_DIR = PROJECT_ROOT / "data" / "processed" / "chunks_legal"

# Subdirectorios de data/raw/ (nombres originales del corpus)
BOE_DIR = "boe"
EU_DIR = "EU AI Act completo (Reglamento UE 2024-1689)"
AESIA_DIR = "Guías AESIA + sandbox regulatorio"
LOPD_DIR = "Normativa LOPD-GDD, RGPD"

# ── Utilidades ──────────────────────────────────────────────────────


def _md5(s: str) -> str:
    return hashlib.md5(s.encode("utf-8")).hexdigest()


def _norm_spaces(s: str) -> str:
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


# ── Lectura de documentos raw ───────────────────────────────────────


def read_html_docs(directory: Path, source: str) -> list[dict]:
    """Lee archivos HTML y extrae texto plano."""
    if not directory.exists():
        print(f"  [WARN] No existe: {directory}")
        return []

    files = sorted(directory.glob("*.html"))
    docs = []
    for fp in files:
        html = fp.read_text(encoding="utf-8", errors="ignore")
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text("\n")
        text = "\n".join(line.strip() for line in text.splitlines() if line.strip())
        docs.append({"source": source, "file": fp.name, "text": text})

    print(f"  {source}: {len(docs)} documentos HTML")
    return docs


def read_pdf_docs(directory: Path, source: str) -> list[dict]:
    """Lee archivos PDF y extrae texto plano."""
    if not directory.exists():
        print(f"  [WARN] No existe: {directory}")
        return []

    files = sorted(directory.glob("*.pdf"))
    docs = []
    for fp in files:
        try:
            reader = PdfReader(str(fp))
            parts = []
            for page in reader.pages:
                t = page.extract_text() or ""
                t = "\n".join(line.strip() for line in t.splitlines() if line.strip())
                if t:
                    parts.append(t)
            docs.append({
                "source": source,
                "file": fp.name,
                "text": "\n\n".join(parts),
            })
        except Exception as e:
            print(f"  [WARN] Error al leer {fp.name}: {e}")

    print(f"  {source}: {len(docs)} documentos PDF")
    return docs


# ── Chunking estructurado (BOE / EU AI Act / AESIA) ────────────────


def _split_units(text: str, patterns: list[str]) -> list[tuple[str, str]]:
    """Divide texto en unidades usando patrones regex de cabeceras."""
    t = "\n" + text.strip() + "\n"
    hits = []
    for pat in patterns:
        for m in re.finditer(pat, t, flags=re.IGNORECASE | re.MULTILINE):
            hits.append((m.start(), m.group(0).strip()))
    hits = sorted(set(hits), key=lambda x: x[0])

    if not hits:
        return [("DOCUMENT", text.strip())]

    units = []
    for i, (pos, header) in enumerate(hits):
        end = hits[i + 1][0] if i + 1 < len(hits) else len(t)
        chunk = t[pos:end].strip()
        first_line = chunk.splitlines()[0].strip() if chunk else header
        body = "\n".join(chunk.splitlines()[1:]).strip()
        units.append((first_line, body if body else chunk))
    return units


def _parse_doc_meta(source: str, file: str, text: str) -> dict:
    """Extrae metadata del documento (titulo, fecha, BOE ID)."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    title = lines[0][:200] if lines else None

    m = re.search(
        r"\b(\d{1,2})\s+de\s+"
        r"(enero|febrero|marzo|abril|mayo|junio|julio|agosto|"
        r"septiembre|setiembre|octubre|noviembre|diciembre)"
        r"\s+de\s+(\d{4})\b",
        text,
        flags=re.IGNORECASE,
    )
    date = f"{m.group(1)} {m.group(2).lower()} {m.group(3)}" if m else None

    boe_id = boe_year = None
    if source == "boe":
        m2 = re.search(r"BOE-[A-Z]-([0-9]{4})-([0-9]+)", file)
        if m2:
            boe_year, boe_id = m2.group(1), m2.group(2)

    return {"doc_title": title, "doc_date": date, "boe_year": boe_year, "boe_id": boe_id}


def _unit_meta(header: str) -> tuple[str, str | None, str]:
    """Clasifica la unidad (article, chapter, section, title) desde el header."""
    h = header.strip()
    unit_title = h[:200]

    m = re.search(r"\b(art[íi]culo|article)\s+(\d+)\b", h, flags=re.IGNORECASE)
    if m:
        return "article", m.group(2), unit_title

    m = re.search(r"\bcap[íi]tulo\s+([ivxlcdm]+|\d+)\b", h, flags=re.IGNORECASE)
    if m:
        return "chapter", m.group(1).upper(), unit_title

    m = re.search(r"\bt[íi]tulo\s+([ivxlcdm]+|\d+)\b", h, flags=re.IGNORECASE)
    if m:
        return "title", m.group(1).upper(), unit_title

    m = re.search(r"\bsecci[oó]n\s+([ivxlcdm]+|\d+)\b", h, flags=re.IGNORECASE)
    if m:
        return "section", m.group(1).upper(), unit_title

    return "section", unit_title.strip() or None, unit_title


# Patrones regex por fuente
BOE_PATTERNS = [
    r"(?m)^\s*Art[íi]culo\s+\d+.*$",
    r"(?m)^\s*T[íi]TULO\s+[IVXLC0-9]+\b.*$",
    r"(?m)^\s*CAP[ÍI]TULO\s+[IVXLC0-9]+\b.*$",
    r"(?m)^\s*Secci[oó]n\s+[IVXLC0-9]+\b.*$",
]
EU_PATTERNS = [
    r"(?m)^\s*Article\s+\d+.*$",
    r"(?m)^\s*Art[íi]culo\s+\d+.*$",
    r"(?m)^\s*CHAPTER\s+[IVXLC0-9]+\b.*$",
    r"(?m)^\s*CAP[ÍI]TULO\s+[IVXLC0-9]+\b.*$",
    r"(?m)^\s*SECTION\s+[IVXLC0-9]+\b.*$",
    r"(?m)^\s*Secci[oó]n\s+[IVXLC0-9]+\b.*$",
]
AESIA_PATTERNS = [
    r"(?m)^\s*T[íi]TULO\s+[IVXLC0-9]+\b.*$",
    r"(?m)^\s*CAP[ÍI]TULO\s+[IVXLC0-9]+\b.*$",
    r"(?m)^\s*Secci[oó]n\s+[IVXLC0-9]+\b.*$",
    r"(?m)^\s*Art[íi]culo\s+\d+.*$",
]


def chunk_docs(source: str, docs: list[dict], patterns: list[str]) -> list[dict]:
    """Genera chunks estructurados a partir de documentos ya leidos."""
    chunks = []
    for doc in docs:
        file = doc["file"]
        text = _norm_spaces(doc["text"])
        dmeta = _parse_doc_meta(source, file, text)
        units = _split_units(text, patterns)

        for u_idx, (header, body) in enumerate(units):
            body = _norm_spaces(body)
            if len(body) < 80:
                continue

            unit_type, unit_id, unit_title = _unit_meta(header)
            chunk = {
                "source": source,
                "file": file,
                "doc_title": dmeta["doc_title"],
                "doc_date": dmeta["doc_date"],
                "boe_year": dmeta["boe_year"],
                "boe_id": dmeta["boe_id"],
                "unit_type": unit_type,
                "unit_id": unit_id,
                "unit_title": unit_title,
                "unit_index": u_idx,
                "text": body,
            }
            chunk["id"] = _md5(
                f"{source}|{file}|{unit_type}|{unit_id}|{u_idx}|{body[:200]}"
            )
            chunks.append(chunk)

    return chunks


# ── Chunking LOPD/RGPD (logica diferente: por articulos) ───────────

_RE_TITULO = re.compile(r"^\s*T[ÍI]TULO\s+([IVXLCDM]+)\b\.?\s*(.*)$", re.IGNORECASE)
_RE_CAPIT = re.compile(r"^\s*CAP[ÍI]TULO\s+([IVXLCDM]+)\b\.?\s*(.*)$", re.IGNORECASE)
_RE_SECC = re.compile(r"^\s*SECCI[ÓO]N\s+([IVXLCDM]+)\b\.?\s*(.*)$", re.IGNORECASE)
_RE_ART = re.compile(r"^\s*Art[íi]culo\s+(\d+)\.?\s*(.*)$", re.IGNORECASE)


def _chunk_by_articles(text: str) -> list[dict]:
    """Divide texto LOPD/RGPD en chunks por articulos."""
    lines = [ln.strip() for ln in text.replace("\ufeff", "").splitlines() if ln.strip()]
    cur = {"titulo": None, "capitulo": None, "seccion": None, "articulo": None}
    buf: list[str] = []
    out: list[dict] = []
    seen_article = False

    def flush():
        nonlocal buf
        if not buf:
            return
        chunk_text = "\n".join(buf).strip()
        if chunk_text:
            out.append({"meta": cur.copy(), "text": chunk_text})
        buf = []

    for ln in lines:
        m = _RE_TITULO.match(ln)
        if m:
            cur["titulo"] = (m.group(1) + (" " + m.group(2) if m.group(2) else "")).strip()
            buf.append(ln)
            continue

        m = _RE_CAPIT.match(ln)
        if m:
            cur["capitulo"] = (m.group(1) + (" " + m.group(2) if m.group(2) else "")).strip()
            buf.append(ln)
            continue

        m = _RE_SECC.match(ln)
        if m:
            cur["seccion"] = (m.group(1) + (" " + m.group(2) if m.group(2) else "")).strip()
            buf.append(ln)
            continue

        m = _RE_ART.match(ln)
        if m:
            if seen_article:
                flush()
            seen_article = True
            cur["articulo"] = m.group(1)
            buf.append(ln)
            continue

        buf.append(ln)

    flush()
    if not out:
        out = [{"meta": cur.copy(), "text": "\n".join(lines)}]
    return out


def chunk_lopd(docs: list[dict]) -> list[dict]:
    """Genera chunks estructurados para LOPD/RGPD."""
    chunks = []
    for doc in docs:
        file = doc["file"]
        raw_chunks = _chunk_by_articles(doc["text"])

        for i, ch in enumerate(raw_chunks):
            txt = ch["text"].strip()
            if not txt:
                continue

            meta = ch["meta"]
            if meta.get("articulo"):
                unit_type = "article"
            elif meta.get("seccion"):
                unit_type = "section"
            elif meta.get("capitulo"):
                unit_type = "chapter"
            elif meta.get("titulo"):
                unit_type = "title"
            else:
                unit_type = None

            unit_id = (
                meta.get("articulo")
                or meta.get("seccion")
                or meta.get("capitulo")
                or meta.get("titulo")
            )
            if meta.get("articulo"):
                unit_title = f"Artículo {meta['articulo']}"
            else:
                unit_title = unit_id or "DOCUMENT"

            chunk = {
                "id": None,
                "source": "lopd_rgpd",
                "file": file,
                "doc_title": file,
                "doc_date": None,
                "boe_id": None,
                "boe_year": None,
                "unit_type": unit_type,
                "unit_id": unit_id,
                "unit_title": unit_title,
                "unit_index": i,
                "text": txt,
            }
            chunk["id"] = _md5(json.dumps(chunk, ensure_ascii=False, sort_keys=True))
            chunks.append(chunk)

    return chunks


# ── Pipeline principal ──────────────────────────────────────────────


def main() -> None:
    print("=== Ingesta de datos legales ===")
    print(f"RAW: {RAW_DIR}")
    print(f"OUT: {OUT_DIR}")

    if not RAW_DIR.exists():
        print(f"\n[ERROR] No existe {RAW_DIR}. Ejecuta 'dvc pull' primero.")
        return

    # 1) Leer documentos raw
    print("\n-- Lectura de documentos --")
    boe_docs = read_html_docs(RAW_DIR / BOE_DIR, "boe")
    eu_docs = read_html_docs(RAW_DIR / EU_DIR, "eu_ai_act")
    aesia_docs = read_pdf_docs(RAW_DIR / AESIA_DIR, "aesia")
    lopd_docs = read_pdf_docs(RAW_DIR / LOPD_DIR, "lopd_rgpd")

    # 2) Chunking estructurado
    print("\n-- Chunking --")
    boe_chunks = chunk_docs("boe", boe_docs, BOE_PATTERNS)
    eu_chunks = chunk_docs("eu_ai_act", eu_docs, EU_PATTERNS)
    aesia_chunks = chunk_docs("aesia", aesia_docs, AESIA_PATTERNS)
    lopd_chunks = chunk_lopd(lopd_docs)

    main_chunks = boe_chunks + eu_chunks + aesia_chunks
    all_chunks = main_chunks + lopd_chunks

    print(f"  BOE: {len(boe_chunks)} chunks")
    print(f"  EU AI Act: {len(eu_chunks)} chunks")
    print(f"  AESIA: {len(aesia_chunks)} chunks")
    print(f"  LOPD/RGPD: {len(lopd_chunks)} chunks")
    print(f"  TOTAL: {len(all_chunks)} chunks")

    # 3) Escribir outputs
    print("\n-- Escritura --")
    out_main = OUT_DIR / "chunks_final.jsonl"
    out_all = OUT_DIR / "chunks_final_all_sources.jsonl"

    _write_jsonl(out_main, main_chunks)
    print(f"  {out_main.name}: {len(main_chunks)} chunks")

    _write_jsonl(out_all, all_chunks)
    print(f"  {out_all.name}: {len(all_chunks)} chunks")

    print("\n=== Ingesta completada ===")


if __name__ == "__main__":
    main()
