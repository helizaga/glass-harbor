import json
import subprocess

import pytest

from glass_harbor import fetch, watch


@pytest.fixture(autouse=True)
def quiet(monkeypatch):
    monkeypatch.setattr(watch, "notify", lambda title, message: None)  # no real macOS notifications from tests


def test_queue_waits_for_both_files_then_mixes(workspace, tmp_path):
    folder = tmp_path / "Downloads"
    folder.mkdir()
    item = watch.add("glock", "for3va jersey", slug="glock-jc")
    assert item["status"] == "waiting" and watch.load_queue()[0]["id"] == "q1"
    calls = []

    def fake_auto(vocal, beat, *, slug, title, log):
        calls.append((vocal, beat, slug))
        return {"slug": slug, "phone": "/runs/glock-jc/mix-phone.m4a", "brief": "brief.md"}

    (folder / "01 - Don Toliver - GLOCK.flac").write_bytes(b"x" * 10)
    assert watch.run_once(folder=folder, settle_s=0, runner=fake_auto) == []  # the beat is not here yet
    (folder / "For3va Jersey Club.mp3").write_bytes(b"y" * 10)
    (folder / "For3va Jersey Club.mp3.crdownload").write_bytes(b"")
    assert watch.run_once(folder=folder, settle_s=0, runner=fake_auto) == []  # still downloading
    (folder / "For3va Jersey Club.mp3.crdownload").unlink()
    handled = watch.run_once(folder=folder, settle_s=0, runner=fake_auto)
    assert handled[0]["status"] == "done" and calls[0][1].endswith("For3va Jersey Club.mp3")
    assert watch.load_queue()[0]["phone"].endswith("mix-phone.m4a")


def test_poor_fit_is_recorded_not_mixed(workspace, tmp_path):
    from glass_harbor.auto import PoorFit

    folder = tmp_path / "dl"
    folder.mkdir()
    (folder / "glock.flac").write_bytes(b"x")
    (folder / "swarm.mp3").write_bytes(b"y")
    watch.add("glock", "swarm")

    def poor(*a, **k):
        raise PoorFit("glock over swarm fails the fit check: crowded vocal range")

    handled = watch.run_once(folder=folder, settle_s=0, runner=poor)
    assert handled[0]["status"] == "poor fit" and "crowded" in handled[0]["reason"]


def test_fetch_takes_only_the_artists_free_download(monkeypatch, tmp_path):
    monkeypatch.setattr(fetch, "_yt_dlp", lambda: "yt-dlp")
    info = {"title": "Beat", "uploader": "DJ", "formats": [{"format_id": "http_mp3_128"}]}
    runs = []

    def fake_run(cmd, **kwargs):
        runs.append(cmd)
        if "--dump-single-json" in cmd:
            return subprocess.CompletedProcess(cmd, 0, json.dumps(info), "")
        return subprocess.CompletedProcess(cmd, 0, str(tmp_path / "DJ - Beat.wav") + "\n", "")

    monkeypatch.setattr(fetch.subprocess, "run", fake_run)
    with pytest.raises(fetch.NoFreeDownload):
        fetch.fetch("https://soundcloud.com/dj/beat", folder=tmp_path, log=lambda m: None)
    assert len(runs) == 1  # never tried to download the stream
    info["formats"].append({"format_id": "download", "ext": "wav"})
    assert fetch.fetch("https://soundcloud.com/dj/beat", folder=tmp_path, log=lambda m: None).name == "DJ - Beat.wav"
    assert runs[-1][runs[-1].index("-f") + 1] == "download"
    with pytest.raises(fetch.NoFreeDownload, match="Bandcamp"):
        fetch.fetch("https://artist.bandcamp.com/track/x", folder=tmp_path, log=lambda m: None)
    with pytest.raises(fetch.NoFreeDownload):
        fetch.fetch("https://www.youtube.com/watch?v=abc", folder=tmp_path, log=lambda m: None)
