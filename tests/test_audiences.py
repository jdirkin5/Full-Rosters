import hashlib

from meta_ads.resources.audiences import hash_rows


def test_hashing_normalizes():
    rows = [{"email": "  Jeff@Example.com ", "phone": "(555) 123-4567"}, {"email": "", "phone": ""}]
    out = hash_rows(rows, ["EMAIL", "PHONE"])
    assert len(out) == 1
    assert out[0][0] == hashlib.sha256(b"jeff@example.com").hexdigest()
    assert out[0][1] == hashlib.sha256(b"5551234567").hexdigest()
