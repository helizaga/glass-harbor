import json

from glass_harbor.cli import main


def _run(capsys, *argv):
    code = main(list(argv))
    out = capsys.readouterr().out
    return code, out


def test_end_to_end_transition(workspace, synth_files, capsys):
    a = synth_files("house-a", 124, "Am", bars=40, seed=1)
    b = synth_files("house-b", 126, "Em", bars=40, seed=2)
    code, out = _run(capsys, "track", "add", str(a["mix"]), "--id", "house-a", "--beats", "librosa", "--json")
    assert code == 0, out
    info = json.loads(out)[0]
    assert abs(info["bpm"] - 124) < 1
    code, _ = _run(capsys, "track", "add", str(b["mix"]), "--id", "house-b", "--beats", "librosa")
    assert code == 0

    code, out = _run(capsys, "match", "house-a", "--json")
    assert code == 0 and json.loads(out)[0]["track"] == "house-b"

    code, out = _run(capsys, "mix", "new", "demo", "--kind", "transition", "--tracks", "house-a", "house-b")
    assert code == 0, out
    assert (workspace / "mixes" / "demo" / "demo.mix.json").exists()
    assert (workspace / "mixes" / "demo" / "demo.brief.md").exists()

    code, out = _run(capsys, "mix", "validate", "demo", "--json")
    assert code == 0 and json.loads(out)["ok"]

    code, out = _run(capsys, "mix", "render", "demo", "--no-mp3", "--json")
    assert code == 0, out
    result = json.loads(out)
    assert result["qa"]["verdict"] in ("pass", "review")
    run = workspace / "runs" / "demo"
    assert any((p / "mix.wav").exists() and (p / "qa.md").exists() for p in run.iterdir())

    code, out = _run(capsys, "mix", "check", "demo")
    assert code == 0 and "verdict" in out


def test_mashup_with_provided_stems(workspace, synth_files, capsys):
    vox = synth_files("vox", 96, "Gm", bars=16, with_vocal=True, seed=3)
    beat = synth_files("beat", 98, "Gm", bars=40, seed=4)
    code, out = _run(capsys, "track", "add", str(vox["mix"]), "--id", "vox", "--stem", f"vocals={vox['vocals']}",
                     "--beats", "librosa")
    assert code == 0, out
    code, out = _run(capsys, "track", "add", str(beat["mix"]), "--id", "beat", "--beats", "librosa")
    assert code == 0, out
    code, out = _run(capsys, "track", "show", "vox", "--json")
    assert json.loads(out)["vocal_phrases"]
    code, out = _run(capsys, "mix", "new", "mash", "--kind", "mashup", "--vocals", "vox", "--bed", "beat")
    assert code == 0, out
    plan = json.loads((workspace / "mixes" / "mash" / "mash.mix.json").read_text())
    assert plan["bpm"] == round(json.loads((workspace / "library" / "beat" / "analysis.json").read_text())["bpm"], 2)
    assert any(c["stem"] == "vocals" for c in plan["clips"])


def test_errors_are_reported_not_raised(workspace, capsys):
    code = main(["mix", "validate", "missing"])
    assert code == 2
    code = main(["track", "show", "nope"])
    assert code == 2
