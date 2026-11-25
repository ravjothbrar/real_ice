"""Merge data/provenance/*.json into data/PROVENANCE.json."""
import json, pathlib
D = pathlib.Path(__file__).resolve().parents[1] / "data"

def build():
    out = {p.stem: json.loads(p.read_text()) for p in sorted((D / "provenance").glob("*.json"))}
    (D / "PROVENANCE.json").write_text(json.dumps(out, indent=2))
    return out

if __name__ == "__main__":
    print(len(build()), "datasets")
