import os, sys, csv
import pytest

sys.path.insert(0, os.path.dirname(__file__))


@pytest.fixture
def write_csv(tmp_path):
    """Écrit un CSV (séparateur ';') dans tmp_path et renvoie son chemin.
    rows = liste de dicts indexés par entête."""
    def _w(name, headers, rows, sep=";"):
        p = tmp_path / name
        with open(p, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, delimiter=sep)
            w.writerow(headers)
            for r in rows:
                w.writerow([r.get(h, "") for h in headers])
        return str(p)
    return _w


def read_csv(path, sep=";"):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=sep))
