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


def _double_time_song(workspace):
    """A 75 bpm vocal (3.2 s bars) with a published hook, a "shoot" chant answered by one-off call lines, an intro,
    and verses; and a 150 bpm beat with drops at 17, 49, and 81."""
    from glass_harbor.lyrics_ref import parse_synced, reference_path

    taste = load_taste()
    taste["defaults"]["dj_edge_bars"] = 0
    save_taste(taste)
    write_fake_track("vox", bpm=75, key="Am", bars=48)
    write_fake_track("beat", bpm=150, key="Am", bars=96, stems=("instrumental",))
    meta = library.load_meta("vox")
    meta["title"] = "Glock Test"
    library.save_meta("vox", meta)
    at = lambda bar: (bar - 1) * 3.2  # noqa: E731
    lines = [(1.0, "intro line number one"), (3.0, "intro line number two"), (5.0, "intro line number three"),
             (7.0, "intro line number four")]
    for cycle in (9.4, 13.4, 25.4, 29.4):
        lines += [(cycle, "hold my glock in the club"), (cycle + 1, "they wanna show me love"), (cycle + 2.5, "oh oh")]
    lines += [(17.4, "first verse line"), (19.4, "second verse line"), (21.4, "third verse line"),
              (23.4, "fourth verse line"), (33.4, "a verse two line")]
    for n, shoot in enumerate((35.9, 37.9, 39.9, 41.9, 43.9, 45.9)):
        lines.append((shoot, "shoot shoot shoot"))
        lines.append((shoot + 1.1, f"call line number {n}"))
    lines[-1] = (47.0, "outro words here")
    lines.sort()
    lrc = "\n".join(f"[{int(at(b) // 60):02d}:{at(b) % 60:05.2f}] {text}" for b, text in lines)
    reference_path("vox").write_text(json.dumps({"source": "test", "lines": parse_synced(lrc)}))
    segments = [{"start": at(b), "end": at(b) + 1.0, "text": text,
                 "words": [{"word": w, "start": at(b) + 0.2 * i, "end": at(b) + 0.2 * i + 0.15, "prob": 1}
                           for i, w in enumerate(text.split())]} for b, text in lines]
    lyrics_path("vox").write_text(json.dumps({"segments": segments}))
    beat = library.load_analysis("beat")
    beat["bar_db"] = [-11.0] * 16 + [-8.0] * 80
    beat["drops"] = [17, 49, 81]
    library.save_analysis("beat", beat)


def test_published_lyrics_give_choruses_a_chant_and_line_aligned_verses(workspace):
    from glass_harbor.arrange import reference_material
    from glass_harbor.grid import Grid

    _double_time_song(workspace)
    material = reference_material("vox", Grid.from_dict(library.load_analysis("vox")["grid"]), 2.0)
    assert material["hook_text"] == "hold my glock in the club" and material["chant_text"] == "shoot shoot shoot"
    # Two whole cycles fill 16 output bars; the line just before bar 9 is not part of it (start at beat 2).
    assert material["choruses"][0] == {"anchor": 9, "start": 9.25, "end": 17}
    chant24, chant16 = material["chants"][0]
    assert chant24["anchor"] == 36 and chant24["start"] == 35.75  # a pickup into bar 36
    assert chant16["end"] == 43.0  # ends after a "shoot", never on the call line that sets up the next one
    first, second = material["verses"][:2]
    assert first["start"] == 17.25 and first["end"] == second["start"] == 21.25  # seamless back to back
    assert material["intro"][-1]["anchor"] == 5


def test_double_time_draft_puts_hooks_on_drops_and_the_chant_on_the_last(workspace):
    _double_time_song(workspace)
    plan = build_mashup("vox", "beat")
    res = resolve(plan)
    assert res.ok, [i.to_dict() for i in res.issues if i.level == "error"]
    assert not [i for i in res.issues if "overlap" in i.message]
    vocals = {c["id"]: c for c in plan["clips"] if c.get("stem") == "vocals"}
    assert vocals["hook1"]["at_bar"] == 17.5 and vocals["hook2"]["at_bar"] == 49.5  # bar 9 on the drop, sung from beat 2
    assert vocals["chant1"]["at_bar"] == 81 and vocals["chant1"]["pre_beats"] == 1
    assert vocals["intro1"]["at_bar"] + vocals["intro1"]["bars"] * 2 <= 17.5  # the intro leads into the first drop
    assert any("chant takes the bar-81 drop" in n for n in plan["notes"])
