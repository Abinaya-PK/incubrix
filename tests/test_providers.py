from app.providers import (get_asr, get_footage, get_generative, get_judge,
                           get_llm, get_tts)


def test_asr_returns_ordered_words():
    words = get_asr().transcribe("anything.wav")
    assert len(words) > 3
    assert all(w.end > w.start for w in words)
    assert all(a.end <= b.start + 1e-6 for a, b in zip(words, words[1:]))


def test_tts_writes_file(tmp_path):
    out = get_tts().speak("hello there world", "en-IN-female", str(tmp_path / "a.wav"))
    assert (tmp_path / "a.wav").stat().st_size > 1000
    assert out.endswith("a.wav")


def test_llm_returns_queries():
    r = get_llm().analyze_scene("Saving money", visual_hint="coins in a jar")
    assert r["queries"] and r["queries"][0] == "coins in a jar"


def test_footage_is_licence_clean():
    cands = get_footage().search("money")
    assert len(cands) >= 3
    assert all(c.commercial_ok and not c.watermark for c in cands)
    assert len({c.id for c in cands}) == len(cands)


def test_generative_is_flagged():
    assert get_generative().generate("a jar of coins", 4.0).ai_generated is True


def test_judge_range():
    assert 1 <= get_judge().score("x.mp4", "text") <= 5