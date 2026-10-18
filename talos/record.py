"""Record raw tracked points (never video) to compressed JSON Lines, and read them back for replay."""
import gzip
import json

from talos.vision import Frame


def _round(v):
    return [_round(x) for x in v] if isinstance(v, list) else round(v, 4)


class Recorder:
    def __init__(self, path):
        try:
            self.file = gzip.open(path, "xt")  # "x": never overwrite an earlier recording
        except FileExistsError:
            raise SystemExit(f"{path} already exists; pick another name so it isn't overwritten.") from None

    def write(self, f):
        line = {"t": round(f.t, 4), "aspect": round(f.aspect, 4), "idle": round(f.idle, 2),
                "motion": [round(f.motion[0], 3), None if f.motion[1] is None else round(f.motion[1], 3)],
                "hands": [{"side": h["side"], "pts": _round(h["pts"]),
                           **({"world": _round(h["world"])} if "world" in h else {})} for h in f.hands],
                "body": _round(f.body) if f.body else None}
        self._line(line)

    def label(self, gesture, start, end):
        """What the user was asked to do between start and end ("nothing" = no gesture should fire)."""
        self._line({"prompt": gesture, "start": round(start, 4), "end": round(end, 4)})

    def _line(self, d):
        self.file.write(json.dumps(d, separators=(",", ":")) + "\n")

    def close(self):
        self.file.close()


def read(path):
    with gzip.open(path, "rt") as file:
        for line in file:
            d = json.loads(line)
            if "prompt" in d:
                continue
            # Recordings before the motion signal have none; replay them as "no motion".
            yield Frame(d["t"], d["aspect"], d["hands"], d["body"], d["idle"], tuple(d.get("motion", (0.0, None))))


def labels(path):
    """[(start, end, gesture)] from a `talos collect` recording."""
    with gzip.open(path, "rt") as file:
        return [(d["start"], d["end"], d["prompt"]) for d in map(json.loads, file) if "prompt" in d]
