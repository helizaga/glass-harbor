import json

from conftest import write_fake_track

from glass_harbor import library
from glass_harbor.feedback import load_taste, save_taste
from glass_harbor.lyrics import lyrics_path
from glass_harbor.plan import resolve
from glass_harbor.scaffold import build_mashup


def _setup(workspace):
    taste = load_taste()
    taste["defaults"]["dj_edge_bars"] = 0  # keep bar numbers easy to read in this test
    save_taste(taste)
    write_fake_track("vox", bpm=120, key="Am", bars=40)
    write_fake_track("beat", bpm=120, key="Am", bars=80, stems=("instrumental",))
    meta = library.load_meta("vox")
    meta["title"] = "Janice Test"
    library.save_meta("vox", meta)
    bar = 2.0  # seconds per bar at 120 bpm

    def seg(start_bar, text):
        t0 = (start_bar - 1) * bar
        words = [{"word": w, "start": t0 + 0.4 * i, "end": t0 + 0.4 * i + 0.35, "prob": 1} for i, w in enumerate(text.split())]
        return {"start": words[0]["start"], "end": words[-1]["end"], "text": text, "words": words}

    lines = [seg(b, "a million things i said") for b in (1, 3, 5, 7)]
    lines += [seg(b, "call my phone baby") for b in (10, 26)]
    lines += [seg(b, "you know the deal baby") for b in (12, 14, 28, 30)]
    lines += [seg(b, "running it up every night") for b in (18, 20, 22, 34, 36)]
    lines += [seg(24, "hey janice")]
    lyrics_path("vox").write_text(json.dumps({"segments": sorted(lines, key=lambda s: s["start"])}))
    vox = library.load_analysis("vox")
    vox["stems"]["vocals"]["phrases"] = [{"start_bar": 1, "bars": 8}, {"start_bar": 10, "bars": 8},
                                         {"start_bar": 18, "bars": 8}, {"start_bar": 26, "bars": 12}]
    library.save_analysis("vox", vox)
    beat = library.load_analysis("beat")
    levels = [-8.0] * 80
    for b in range(17, 25):
        levels[b - 1] = -14.0  # breakdown
    for b in range(49, 57):
        levels[b - 1] = -14.0  # breakdown
    for b in (59, 60):
        levels[b - 1] = -26.0  # near-silent break before a drop
    beat["bar_db"] = levels
    beat["drops"] = [25, 61]
    library.save_analysis("beat", beat)


def test_structure_aware_draft(workspace):
    _setup(workspace)
    plan = build_mashup("vox", "beat")
    res = resolve(plan)
    assert res.ok, [i.to_dict() for i in res.issues if i.level == "error"]
    vocals = {c["id"]: c for c in plan["clips"] if c.get("stem") == "vocals"}
    hooks = sorted(c["at_bar"] for c in vocals.values() if c.get("chain") == "hook")
    assert 25 in hooks and 61 in hooks  # choruses land on the drops
    assert vocals["title-break"]["at_bar"] + vocals["title-break"]["bars"] == 61  # spotlight ends on the drop
    assert any(c["id"].startswith("chops") and 17 <= c["at_bar"] < 25 for c in vocals.values())  # breakdown
    assert any(c["id"].startswith("verse") and c["at_bar"] == 9 for c in vocals.values())
    assert not any(c.get("generate") == "snare_roll" and 57 <= c["at_bar"] < 61 for c in plan["clips"])
    assert any(n.startswith("structure-aware draft") for n in plan["notes"])


def test_hook_ending_on_the_next_drop_does_not_hang(workspace):
    import signal

    _setup(workspace)
    beat = library.load_analysis("beat")
    beat["drops"] = [25, 33]  # the 8-bar hook on the bar-25 drop ends exactly on the next drop
    library.save_analysis("beat", beat)

    def timeout(*_):
        raise TimeoutError("build_mashup looped")

    previous = signal.signal(signal.SIGALRM, timeout)
    signal.alarm(30)
    try:
        plan = build_mashup("vox", "beat")
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)
    assert resolve(plan).ok
