"""The one event shape every gesture uses."""
from dataclasses import dataclass, field


@dataclass
class Event:
    gesture: str
    phase: str          # once | begin | update | end
    t: float
    side: str | None = None
    data: dict = field(default_factory=dict)
    score: float = 0    # tiebreaker points: how many (weighted) conditions the match met
    began: float | None = None  # when the gesture's start pose appeared; on a points tie the earlier one wins

    def __str__(self):
        extra = f" {self.data}" if self.data else ""
        return f"{self.t:7.2f}s {self.gesture} {self.phase}{f' ({self.side})' if self.side else ''}{extra}"
