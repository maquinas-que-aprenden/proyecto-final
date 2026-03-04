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
from langchain_text_splitters import RecursiveCharacterTextSplitter
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

# ── Límites de chunk ───────────────────────────────────────────────
MAX_CHUNK_CHARS = 2000   # ~500 tokens para e5-base (512 token limit)
MIN_CHUNK_CHARS = 80     # Mínimo viable
CHUNK_OVERLAP = 200      # Overlap para secondary splitter

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


# ── Chunking estructurado ─────────────────────────────────────────


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

    meta = {"doc_title": title, "doc_date": date}

    # Campos específicos BOE (solo cuando aplica)
    if source == "boe":
        m2 = re.search(r"BOE-[A-Z]-([0-9]{4})-([0-9]+)", file)
        if m2:
            meta["boe_year"] = m2.group(1)
            meta["boe_id"] = m2.group(2)

    return meta


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


def _unit_meta_aesia(header: str) -> tuple[str, str | None, str]:
    """Clasifica unidad AESIA por numeración decimal: 1. → chapter, 1.1 → section, 1.1.1 → subsection."""
    h = header.strip()
    unit_title = h[:200]

    m = re.match(r"^\s*(\d{1,2})\.(\d{1,2})\.(\d{1,2})", h)
    if m:
        return "subsection", f"{m.group(1)}.{m.group(2)}.{m.group(3)}", unit_title

    m = re.match(r"^\s*(\d{1,2})\.(\d{1,2})", h)
    if m:
        return "section", f"{m.group(1)}.{m.group(2)}", unit_title

    m = re.match(r"^\s*(\d{1,2})\.\s+", h)
    if m:
        return "chapter", m.group(1), unit_title

    return "section", unit_title.strip() or None, unit_title


_resplitter = RecursiveCharacterTextSplitter(
    chunk_size=MAX_CHUNK_CHARS,
    chunk_overlap=CHUNK_OVERLAP,
    separators=["\n\n", "\n", ". ", " "],
)


def _resplit_if_needed(text: str) -> list[str]:
    """Si el texto excede MAX_CHUNK_CHARS, lo divide con RecursiveCharacterTextSplitter."""
    if len(text) <= MAX_CHUNK_CHARS:
        return [text]
    return _resplitter.split_text(text)


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
    r"(?m)^\s*(\d{1,2})\.\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÁÉÍÓÚÑ\s]{5,}$",
    r"(?m)^\s*\d{1,2}\.\d{1,2}\.?\s+[A-ZÁÉÍÓÚÑ].*$",
    r"(?m)^\s*\d{1,2}\.\d{1,2}\.\d{1,2}\.?\s+[A-ZÁÉÍÓÚÑ].*$",
]


def chunk_docs(
    source: str,
    docs: list[dict],
    patterns: list[str],
    unit_meta_fn=None,
) -> list[dict]:
    """Genera chunks estructurados a partir de documentos ya leidos."""
    if unit_meta_fn is None:
        unit_meta_fn = _unit_meta

    chunks = []
    for doc in docs:
        file = doc["file"]
        text = _norm_spaces(doc["text"])
        dmeta = _parse_doc_meta(source, file, text)
        units = _split_units(text, patterns)

        for u_idx, (header, body) in enumerate(units):
            body = _norm_spaces(body)
            if len(body) < MIN_CHUNK_CHARS:
                continue

            unit_type, unit_id, unit_title = unit_meta_fn(header)

            sub_parts = _resplit_if_needed(body)
            for sub_i, sub_text in enumerate(sub_parts):
                sub_text = sub_text.strip()
                if len(sub_text) < MIN_CHUNK_CHARS:
                    continue

                chunk = {
                    "source": source,
                    "file": file,
                    "doc_title": dmeta["doc_title"],
                    "doc_date": dmeta["doc_date"],
                    "unit_type": unit_type,
                    "unit_id": unit_id,
                    "unit_title": unit_title,
                    "unit_index": u_idx,
                    "sub_index": sub_i,
                    "text": sub_text,
                }
                # Campos específicos BOE
                if "boe_year" in dmeta:
                    chunk["boe_year"] = dmeta["boe_year"]
                if "boe_id" in dmeta:
                    chunk["boe_id"] = dmeta["boe_id"]
                chunk["id"] = _md5(
                    f"{source}|{file}|{unit_type}|{unit_id}|{u_idx}|{sub_i}|{sub_text[:200]}"
                )
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

    # 2) Chunking estructurado (todas las fuentes usan chunk_docs)
    print("\n-- Chunking --")
    boe_chunks = chunk_docs("boe", boe_docs, BOE_PATTERNS)
    eu_chunks = chunk_docs("eu_ai_act", eu_docs, EU_PATTERNS)
    aesia_chunks = chunk_docs("aesia", aesia_docs, AESIA_PATTERNS, unit_meta_fn=_unit_meta_aesia)
    lopd_chunks = chunk_docs("lopd_rgpd", lopd_docs, BOE_PATTERNS)

    all_chunks = boe_chunks + eu_chunks + aesia_chunks + lopd_chunks

    if not all_chunks:
        print("\n[ERROR] No se generaron chunks. Revisa rutas de data/raw y patrones de chunking.")
        return

    print(f"  BOE: {len(boe_chunks)} chunks")
    print(f"  EU AI Act: {len(eu_chunks)} chunks")
    print(f"  AESIA: {len(aesia_chunks)} chunks")
    print(f"  LOPD/RGPD: {len(lopd_chunks)} chunks")
    print(f"  TOTAL: {len(all_chunks)} chunks")

    # 3) Escribir output
    print("\n-- Escritura --")
    out_path = OUT_DIR / "chunks_final_all_sources.jsonl"
    _write_jsonl(out_path, all_chunks)
    print(f"  {out_path.name}: {len(all_chunks)} chunks")

    # 4) Verificación
    sizes = [len(c["text"]) for c in all_chunks]
    over = sum(1 for s in sizes if s > MAX_CHUNK_CHARS)
    under = sum(1 for s in sizes if s < MIN_CHUNK_CHARS)
    print("\n-- Verificación --")
    print(f"  Max chunk: {max(sizes)} chars (límite: {MAX_CHUNK_CHARS})")
    print(f"  Min chunk: {min(sizes)} chars (límite: {MIN_CHUNK_CHARS})")
    print(f"  >MAX: {over} (debe ser 0)")
    print(f"  <MIN: {under} (debe ser 0)")

    print("\n=== Ingesta completada ===")


if __name__ == "__main__":
    main()
