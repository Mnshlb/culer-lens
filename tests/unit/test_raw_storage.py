import hashlib
import time

from barca.data.load import _sha256, _write_gz


def test_identical_payloads_give_identical_files(tmp_path):
    payload = b'{"id": 1, "type": "Pass"}' * 100
    a, b = tmp_path / "a" / "x.json.gz", tmp_path / "b" / "x.json.gz"
    _write_gz(a, payload)
    time.sleep(1.1)  # a gzip header timestamp would now differ
    _write_gz(b, payload)
    assert a.read_bytes() == b.read_bytes()


def test_checksum_describes_content_not_compression(tmp_path):
    payload = b"Div,Date,HomeTeam,AwayTeam\nSP1,15/08/2026,Alaves,Getafe\n"
    gz, plain = tmp_path / "f.csv.gz", tmp_path / "f.csv"
    _write_gz(gz, payload)
    plain.write_bytes(payload)
    expected = hashlib.sha256(payload).hexdigest()
    assert _sha256(gz) == _sha256(plain) == expected
