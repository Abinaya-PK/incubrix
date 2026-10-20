from dataclasses import dataclass

from app.providers.base import Word

SENTENCE_END = (".", "!", "?", "।")
CLAUSE_END = (",", ";", ":")


@dataclass
class Scene:
    index: int
    text: str
    start: float
    end: float
    words: list[Word]

    @property
    def duration(self) -> float:
        return self.end - self.start


def _split_at(words: list[Word], endings: tuple) -> list[list[Word]]:
    groups, cur = [], []
    for w in words:
        cur.append(w)
        if w.text.endswith(endings):
            groups.append(cur)
            cur = []
    if cur:
        groups.append(cur)
    return groups


def _dur(group: list[Word]) -> float:
    return group[-1].end - group[0].start


def _split_long(group: list[Word], max_s: float) -> list[list[Word]]:
    """Split an over-long group at clause marks, then evenly by words."""
    if _dur(group) <= max_s:
        return [group]
    parts = _split_at(group, CLAUSE_END)
    if len(parts) == 1:
        n = int(_dur(group) // max_s) + 1
        size = max(1, len(group) // n)
        parts = [group[i:i + size] for i in range(0, len(group), size)]
    out = []
    for p in parts:
        out.extend([p] if _dur(p) <= max_s or len(p) == 1 else _split_long(p, max_s))
    return out


def _merge_short(groups: list[list[Word]], min_s: float, max_s: float) -> list[list[Word]]:
    out: list[list[Word]] = []
    for g in groups:
        if out and (_dur(out[-1]) < min_s) and _dur(out[-1] + g) <= max_s:
            out[-1] = out[-1] + g
        else:
            out.append(g)
    # fold a short last group into the previous one
    if len(out) > 1 and _dur(out[-1]) < min_s:
        out[-2] = out[-2] + out[-1]
        out.pop()
    return out


def segment(words: list[Word], audio_end: float,
            min_s: float = 2.5, max_s: float = 8.0) -> list[Scene]:
    """Split timed words into contiguous scenes covering 0..audio_end."""
    if not words:
        return []
    groups: list[list[Word]] = []
    for sentence in _split_at(words, SENTENCE_END):
        groups.extend(_split_long(sentence, max_s))
    groups = _merge_short(groups, min_s, max_s)

    scenes = []
    for i, g in enumerate(groups):
        start = 0.0 if i == 0 else scenes[-1].end
        if i + 1 < len(groups):
            nxt = groups[i + 1][0].start
            end = round((g[-1].end + nxt) / 2, 3)   # cut in the middle of the pause
        else:
            end = round(audio_end, 3)
        scenes.append(Scene(i, " ".join(w.text for w in g), round(start, 3), end, g))
    return scenes