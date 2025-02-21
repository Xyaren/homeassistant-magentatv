import hashlib


def magenta_hash(data: str) -> str:
    return hashlib.md5(data.encode("UTF-8")).hexdigest().upper()
