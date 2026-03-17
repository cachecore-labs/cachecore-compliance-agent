"""Single source of truth for the system prompt.

CacheCore derives system_fp = SHA256(this text) for namespace isolation.
ANY byte difference (trailing space, newline, encoding) across agents or
frameworks will produce a different namespace and break L2 matching.

Import this constant everywhere — never copy-paste the string.
"""

SYSTEM_PROMPT: str = (
    "You are a contract compliance analyst. "
    "Review the contract excerpt provided and answer the compliance question concisely. "
    "Respond in 1-2 sentences maximum."
)
