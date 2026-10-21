"""Split a document into passages small enough to embed and retrieve.

Paragraph boundaries are the unit: a passage never starts mid-paragraph when the
document has blank-line structure. A single paragraph longer than ``size`` stays
whole rather than being cut, so the stored text always reads as prose.
"""


def chunk_text(text: str, size: int = 800) -> list[str]:
    """Group paragraphs into chunks of at most roughly ``size`` characters."""
    paragraphs = [paragraph.strip() for paragraph in text.split("\n\n") if paragraph.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if current and len(current) + len(paragraph) + 2 > size:
            chunks.append(current)
            current = paragraph
        else:
            current = f"{current}\n\n{paragraph}" if current else paragraph
    if current:
        chunks.append(current)
    return chunks
