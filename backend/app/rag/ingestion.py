"""
Document Ingestion
---------------------
Doc-aware chunking: splits on paragraph boundaries first, respects line
boundaries for structured tabular/sheet content, tracks active section locations,
and only falls back to character splitting for lines longer than `max_chars`.
Each chunk keeps its source document name and sequence index so the Response
Generation node can cite "Q3_Budget.pdf, chunk 2, Balance Sheet".
"""
from __future__ import annotations

import re
import uuid

from app.rag.vectorstore import DocumentChunk


def chunk_document(
    text: str,
    source: str,
    max_chars: int = 800,
    overlap: int = 100,
    metadata: dict | None = None,
) -> list[DocumentChunk]:
    if max_chars <= 0:
        raise ValueError("max_chars must be positive")
    if overlap < 0 or overlap >= max_chars:
        raise ValueError("overlap must be >= 0 and < max_chars")

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    raw_chunks: list[tuple[str, str]] = []
    buffer = ""
    current_location = ""
    marker_re = re.compile(r"=== (?:Sheet|Page|Table): ([^=\n]+) ===")

    for para in paragraphs:
        marker_match = marker_re.search(para)
        if marker_match:
            new_location = marker_match.group(1).strip()
            if buffer and new_location != current_location:
                raw_chunks.append((buffer, current_location))
                buffer = ""
            current_location = new_location

        if len(para) > max_chars:
            if buffer:
                raw_chunks.append((buffer, current_location))
                buffer = ""

            lines = para.splitlines()
            if len(lines) > 1:
                cur_lines: list[str] = []
                cur_len = 0
                header = lines[0] if marker_re.search(lines[0]) else ""
                col_header = lines[1] if (len(lines) > 1 and lines[1].startswith("Row 1:")) else ""
                context_prefix = f"[{current_location}] " if current_location else ""

                for line in lines:
                    line_len = len(line) + 1
                    if cur_len + line_len > max_chars and cur_lines:
                        raw_chunks.append(("\n".join(cur_lines), current_location))
                        cur_lines = []
                        cur_len = 0
                        if col_header and line != col_header and line != header:
                            cur_lines.append(f"{context_prefix}{col_header} (cont.)")
                            cur_len += len(cur_lines[0]) + 1

                    if line_len > max_chars:
                        start = 0
                        while start < len(line):
                            end = start + max_chars
                            raw_chunks.append((line[start:end], current_location))
                            start = max(start + 1, end - overlap)
                    else:
                        cur_lines.append(line)
                        cur_len += line_len
                if cur_lines:
                    raw_chunks.append(("\n".join(cur_lines), current_location))
            else:
                start = 0
                while start < len(para):
                    end = start + max_chars
                    raw_chunks.append((para[start:end], current_location))
                    start = max(start + 1, end - overlap)
            continue

        candidate = f"{buffer}\n\n{para}".strip() if buffer else para
        if len(candidate) <= max_chars:
            buffer = candidate
        else:
            if buffer:
                raw_chunks.append((buffer, current_location))
            buffer = para

    if buffer:
        raw_chunks.append((buffer, current_location))

    total = len(raw_chunks)
    base_metadata = dict(metadata or {})
    return [
        DocumentChunk(
            id=str(uuid.uuid4()),
            text=chunk_text,
            source=source,
            metadata={
                **base_metadata,
                "chunk_index": i,
                "total_chunks": total,
                "source": source,
                "source_location": loc,
            },
        )
        for i, (chunk_text, loc) in enumerate(raw_chunks)
    ]
