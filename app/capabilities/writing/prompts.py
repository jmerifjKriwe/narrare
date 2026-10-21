"""The continuity prompt. Writing owns its prompt text, per the spec.

The tail of the chapter is the context: enough to pick up voice and situation,
bounded so a long chapter does not grow the request without limit.
"""

MAX_CONTEXT_CHARS = 4000


def continuity_prompt(*, novel_title: str, chapter_title: str, body: str) -> str:
    context = body[-MAX_CONTEXT_CHARS:]
    return (
        f"Novel: {novel_title}\n"
        f"Chapter: {chapter_title}\n\n"
        f"Text so far:\n{context}\n\n"
        "Continue the chapter in the same voice. Keep the language of the existing "
        "text. Return only the new text, without a heading or commentary."
    )
