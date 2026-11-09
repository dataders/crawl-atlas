"""Package finished boards in small groups to keep the Pages file count manageable."""
import json
import sys
from itertools import groupby
from pathlib import Path


def pack(source, output):
    output.mkdir(parents=True, exist_ok=True)
    for prefix, files in groupby(sorted(source.glob("*.html.gz")), key=lambda p: p.name[:3]):
        index = {}
        payload = bytearray()
        for path in files:
            data = path.read_bytes()
            index[path.name.split(".")[0]] = [len(payload), len(data)]
            payload.extend(data)
        with (output / f"{prefix}.bin").open("wb") as stream:
            stream.write(json.dumps(index, separators=(",", ":")).encode() + b"\n")
            stream.write(payload)


if __name__ == "__main__":
    pack(*map(Path, sys.argv[1:]))
