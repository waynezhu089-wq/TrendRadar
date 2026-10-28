import re


def normalize_symbol(symbol: str, market: str) -> tuple[str, str]:
    code = symbol.strip().upper()
    venue = market.strip().upper()
    if "." in code:
        code, suffix = code.rsplit(".", 1)
        if suffix != venue:
            raise ValueError("Symbol suffix and market do not match")
    if venue not in {"SH", "SZ", "BJ"}:
        raise ValueError("Market must be SH, SZ, or BJ")
    if not re.fullmatch(r"[0-9]{6}", code):
        raise ValueError("A-share symbol must contain exactly six digits")
    prefixes = {"SH": ("6",), "SZ": ("0", "2", "3"), "BJ": ("4", "8", "9")}
    if not code.startswith(prefixes[venue]):
        raise ValueError("Symbol prefix does not match the A-share market")
    return code, venue
