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


_RISK_PATTERNS = {
    "inaceptable": r"\binaceptable\b",
    "alto": r"\balto\s+riesgo\b|\bde\s+alto\s+riesgo\b",
    "limitado": r"\briesgo\s+limitado\b|\blimitado\b",
    "mínimo": r"\briesgo\s+m[íi]nimo\b|\bm[íi]nimo\b",
}


def _extract_risk_levels(text: str) -> list[str]:
    """Detecta niveles de riesgo EU AI Act mencionados en el texto."""
    return [
        label
        for label, pat in _RISK_PATTERNS.items()
        if re.search(pat, text, flags=re.IGNORECASE)
    ]


# ── Metadata específica por fuente ─────────────────────────────────

# Mapeo artículo → campo temático (EU AI Act 2024/1689)
_EU_CAMPO_MAP: list[tuple[range, str]] = [
    (range(1, 5),    "definiciones_ambito"),        # Art. 1–4
    (range(5, 6),    "practicas_prohibidas"),        # Art. 5
    (range(6, 50),   "sistemas_alto_riesgo"),        # Art. 6–49
    (range(50, 51),  "transparencia"),               # Art. 50
    (range(51, 57),  "modelos_ia_proposito_general"),# Art. 51–56
    (range(57, 69),  "gobernanza"),                  # Art. 57–68
    (range(69, 99),  "responsabilidad_supervision"), # Art. 69–98
    (range(99, 102), "sanciones"),                   # Art. 99–101
]

_AESIA_AMBITO_PATTERNS: dict[str, str] = {
    "alto_riesgo":    r"\balto\s+riesgo\b",
    "transparencia":  r"\btransparencia\b|\bexplicabilidad\b",
    "datos":          r"\bdatos\s+de\s+entrenamiento\b|\bdataset\b|\bcalidad\s+de\s+datos\b",
    "gobernanza":     r"\bgobernanza\b|\bcumplimiento\b|\bauditoria\b",
    "derechos":       r"\bderechos\s+fundamentales\b|\bno\s+discriminaci[oó]n\b",
    "ciclo_vida":     r"\bciclo\s+de\s+vida\b|\bpost.mercado\b|\bdespliegue\b",
}


def _extra_meta_eu_ai_act(unit_type: str, unit_id: str | None) -> dict:
    """Campos adicionales para chunks de EU AI Act."""
    if unit_type != "article" or not unit_id or not unit_id.isdigit():
        return {}
    n = int(unit_id)
    for art_range, campo in _EU_CAMPO_MAP:
        if n in art_range:
            return {"campo": campo}
    return {"campo": "otros"}


def _extra_meta_aesia(file: str, text: str) -> dict:
    """Campos adicionales para chunks de AESIA."""
    fname = file.lower()
    tipo = "sandbox" if "sandbox" in fname else "guia"
    ambitos = [
        t for t, pat in _AESIA_AMBITO_PATTERNS.items()
        if re.search(pat, text, flags=re.IGNORECASE)
    ]
    meta: dict = {"tipo_documento": tipo}
    if ambitos:
        meta["ambito_tematico"] = ambitos
    return meta


# Patrones BOE
_BOE_TIPO_NORMA_PATTERNS: list[tuple[str, str]] = [
    (r"\bLey\s+Org[áa]nica\b",    "Ley Orgánica"),
    (r"\bReal\s+Decreto-ley\b",   "Real Decreto-ley"),
    (r"\bReal\s+Decreto\b",       "Real Decreto"),
    (r"\bOrden\s+Ministerial\b",  "Orden Ministerial"),
    (r"\bOrden\b",                "Orden"),
    (r"\bResoluci[oó]n\b",        "Resolución"),
    (r"\bLey\b",                  "Ley"),
]

_BOE_ORGANISMO_PATTERNS: list[tuple[str, str]] = [
    (r"Ministerio\s+de\s+([\wáéíóúüñÁÉÍÓÚÜÑ\s]+?)(?:\.|,|\n)", "Ministerio de {0}"),
    (r"Agencia\s+Española\s+de\s+([\wáéíóúüñÁÉÍÓÚÜÑ\s]+?)(?:\.|,|\n)", "Agencia Española de {0}"),
    (r"Consejo\s+de\s+Ministros", "Consejo de Ministros"),
    (r"Jefatura\s+del\s+Estado",  "Jefatura del Estado"),
]

_LOPD_DERECHOS_PATTERNS: dict[str, str] = {
    "acceso":        r"\bderecho\s+de\s+acceso\b",
    "rectificacion": r"\brectificaci[oó]n\b",
    "supresion":     r"\bsupresi[oó]n\b|\bderecho\s+al\s+olvido\b",
    "portabilidad":  r"\bportabilidad\b",
    "oposicion":     r"\boposici[oó]n\b",
    "limitacion":    r"\blimitaci[oó]n\s+del\s+tratamiento\b",
}

_LOPD_CATEGORIA_ESPECIAL_PATTERNS: dict[str, str] = {
    "salud":      r"\bdatos\s+de\s+salud\b|\bhistorial\s+cl[íi]nico\b",
    "biometrico": r"\bdatos\s+biom[eé]tricos\b",
    "ideologia":  r"\bideolog[íi]a\b|\bopini[oó]n\s+pol[íi]tica\b",
    "religion":   r"\bconvicciones\s+religiosas?\b",
    "origen":     r"\borigen\s+(racial|[eé]tnico)\b",
}


def _extra_meta_boe(doc_text: str, chunk_text: str) -> dict:
    """Campos adicionales para chunks de BOE."""
    meta: dict = {}

    # tipo_norma: busca en el texto completo del documento (cabecera)
    header = doc_text[:500]
    for pat, label in _BOE_TIPO_NORMA_PATTERNS:
        if re.search(pat, header, flags=re.IGNORECASE):
            meta["tipo_norma"] = label
            break

    # num_norma: número oficial de la norma (ej: "LO 3/2018", "RD 1112/2018")
    m = re.search(
        r"\b(Ley\s+Org[áa]nica|Ley|Real\s+Decreto-ley|Real\s+Decreto|Orden)\s+(\d+/\d{4})\b",
        header,
        flags=re.IGNORECASE,
    )
    if m:
        meta["num_norma"] = f"{m.group(1).strip()} {m.group(2)}"

    # organismo_emisor: quién emite la norma
    for pat, template in _BOE_ORGANISMO_PATTERNS:
        m2 = re.search(pat, header, flags=re.IGNORECASE)
        if m2:
            if "{0}" in template:
                nombre = m2.group(1).strip().rstrip(".,")
                meta["organismo_emisor"] = template.format(nombre)
            else:
                meta["organismo_emisor"] = template
            break

    return meta


def _extra_meta_lopd_rgpd(file: str, text: str) -> dict:
    """Campos adicionales para chunks de LOPD/RGPD."""
    fname = file.lower()
    meta: dict = {
        "sub_fuente": "lopd_gdd" if "lopdgdd" in fname or "lopd" in fname else "rgpd",
    }

    derechos = [
        d for d, pat in _LOPD_DERECHOS_PATTERNS.items()
        if re.search(pat, text, flags=re.IGNORECASE)
    ]
    if derechos:
        meta["derechos_arco"] = derechos

    categorias = [
        c for c, pat in _LOPD_CATEGORIA_ESPECIAL_PATTERNS.items()
        if re.search(pat, text, flags=re.IGNORECASE)
    ]
    if categorias:
        meta["categoria_dato_especial"] = categorias

    return meta


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
) -> tuple[list[dict], list[dict]]:
    """Genera chunks estructurados a partir de documentos ya leidos.

    Devuelve (chunks, padres):
    - chunks: hijos + singles, listos para indexar en ChromaDB
    - padres: texto completo de unidades que se subdividieron (lookup para RAG)
    """
    if unit_meta_fn is None:
        unit_meta_fn = _unit_meta

    chunks = []
    padres = []

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
            es_subdividido = len(sub_parts) > 1

            if es_subdividido:
                parent_id = _md5(f"{source}|{file}|{unit_type}|{unit_id}|{u_idx}")
                padres.append({
                    "parent_id": parent_id,
                    "source": source,
                    "file": file,
                    "unit_type": unit_type,
                    "unit_id": unit_id,
                    "unit_title": unit_title,
                    "text": body,
                })
            else:
                parent_id = None

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
                    "tipo_nodo": "hijo" if es_subdividido else "single",
                    "parent_id": parent_id,
                    "nivel_riesgo_mencionado": _extract_risk_levels(sub_text),
                    "text": sub_text,
                }
                # Campos específicos BOE
                if "boe_year" in dmeta:
                    chunk["boe_year"] = dmeta["boe_year"]
                if "boe_id" in dmeta:
                    chunk["boe_id"] = dmeta["boe_id"]
                # Campos específicos por fuente
                if source == "eu_ai_act":
                    chunk.update(_extra_meta_eu_ai_act(unit_type, unit_id))
                elif source == "aesia":
                    chunk.update(_extra_meta_aesia(file, sub_text))
                elif source == "boe":
                    chunk.update(_extra_meta_boe(text, sub_text))
                elif source == "lopd_rgpd":
                    chunk.update(_extra_meta_lopd_rgpd(file, sub_text))
                chunk["id"] = _md5(
                    f"{source}|{file}|{unit_type}|{unit_id}|{u_idx}|{sub_i}|{sub_text[:200]}"
                )
                chunks.append(chunk)

    return chunks, padres


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
    boe_chunks, boe_padres = chunk_docs("boe", boe_docs, BOE_PATTERNS)
    eu_chunks, eu_padres = chunk_docs("eu_ai_act", eu_docs, EU_PATTERNS)
    aesia_chunks, aesia_padres = chunk_docs("aesia", aesia_docs, AESIA_PATTERNS, unit_meta_fn=_unit_meta_aesia)
    lopd_chunks, lopd_padres = chunk_docs("lopd_rgpd", lopd_docs, BOE_PATTERNS)

    all_chunks = boe_chunks + eu_chunks + aesia_chunks + lopd_chunks
    all_padres = boe_padres + eu_padres + aesia_padres + lopd_padres

    if not all_chunks:
        print("\n[ERROR] No se generaron chunks. Revisa rutas de data/raw y patrones de chunking.")
        return

    hijos = [c for c in all_chunks if c["tipo_nodo"] == "hijo"]
    singles = [c for c in all_chunks if c["tipo_nodo"] == "single"]
    print(f"  BOE: {len(boe_chunks)} chunks ({len(boe_padres)} padres)")
    print(f"  EU AI Act: {len(eu_chunks)} chunks ({len(eu_padres)} padres)")
    print(f"  AESIA: {len(aesia_chunks)} chunks ({len(aesia_padres)} padres)")
    print(f"  LOPD/RGPD: {len(lopd_chunks)} chunks ({len(lopd_padres)} padres)")
    print(f"  TOTAL: {len(all_chunks)} chunks ({len(singles)} singles, {len(hijos)} hijos, {len(all_padres)} padres)")

    # 3) Escribir output
    print("\n-- Escritura --")
    out_path = OUT_DIR / "chunks_final_all_sources.jsonl"
    _write_jsonl(out_path, all_chunks)
    print(f"  {out_path.name}: {len(all_chunks)} chunks")

    padres_path = OUT_DIR / "chunks_padres.jsonl"
    _write_jsonl(padres_path, all_padres)
    print(f"  {padres_path.name}: {len(all_padres)} padres")

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
