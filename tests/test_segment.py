from app.pipeline.segment import segment
from app.providers.base import Word


def make_words(text, step=0.4):
    out, t = [], 0.0
    for w in text.split():
        out.append(Word(w, round(t, 3), round(t + step, 3)))
        t += step
    return out


def check_contiguous(scenes, audio_end):
    assert scenes[0].start == 0.0
    assert scenes[-1].end == round(audio_end, 3)
    for a, b in zip(scenes, scenes[1:]):
        assert a.end == b.start          # no gap, no overlap
    assert all(s.end > s.start for s in scenes)


def test_splits_on_sentences():
    words = make_words("Saving money is easy. Plan ahead and track every single expense you make. "
                       "Small habits add up over time.")
    end = words[-1].end
    scenes = segment(words, end, min_s=1.0, max_s=8.0)
    assert len(scenes) == 3
    check_contiguous(scenes, end)


def test_merges_short_sentences():
    words = make_words("Hi. Yes. Ok. This is a longer closing sentence for the video.")
    end = words[-1].end
    scenes = segment(words, end, min_s=2.5, max_s=8.0)
    assert all(s.duration >= 2.5 for s in scenes[:-1])
    check_contiguous(scenes, end)


def test_splits_long_sentence():
    text = " ".join(["word"] * 40) + "."
    words = make_words(text)           # 16 seconds
    end = words[-1].end
    scenes = segment(words, end, min_s=2.5, max_s=8.0)
    assert len(scenes) >= 2
    assert all(s.duration <= 8.5 for s in scenes)
    check_contiguous(scenes, end)


def test_every_word_kept_once():
    words = make_words("One two three. Four five six, seven eight nine. Ten eleven twelve.")
    scenes = segment(words, words[-1].end, min_s=1.0, max_s=8.0)
    joined = " ".join(s.text for s in scenes).split()
    assert joined == [w.text for w in words]


def test_empty_words():
    assert segment([], 5.0) == []