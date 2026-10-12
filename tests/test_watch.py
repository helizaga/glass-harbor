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


def test_concurrent_adds_keep_every_pairing(workspace):
    import threading

    threads = [threading.Thread(target=watch.add, args=(f"vocal {i}", f"beat {i}")) for i in range(12)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    items = watch.load_queue()
    assert len(items) == 12 and len({i["id"] for i in items}) == 12
    assert not list(watch.queue_path().parent.glob("queue.json.*.tmp"))  # no temp files left behind


def test_hints_that_match_one_file_wait_for_the_other(workspace, tmp_path):
    folder = tmp_path / "dl"
    folder.mkdir()
    (folder / "DJ remix.mp3").write_bytes(b"x")
    watch.add("dj", "dj remix")
    assert watch.run_once(folder=folder, settle_s=0, runner=lambda *a, **k: {}) == []
    assert watch.load_queue()[0]["status"] == "waiting"


def test_interrupted_runs_are_retried(workspace, tmp_path):
    folder = tmp_path / "dl"
    folder.mkdir()
    (folder / "glock.flac").write_bytes(b"x")
    (folder / "beat.mp3").write_bytes(b"y")
    item = watch.add("glock", "beat")
    watch._update(item["id"], status="running", pid=2 ** 22 + 12345, started_at="2026-01-01T00:00:00")
    handled = watch.run_once(folder=folder, settle_s=0,
                             runner=lambda *a, **k: {"slug": "s", "phone": "p.m4a", "brief": "b.md"})
    assert handled and handled[0]["status"] == "done"


def test_watch_keeps_going_with_an_empty_queue(workspace, tmp_path):
    watch.watch(folder=tmp_path, interval=0, log=lambda m: None, passes=2)  # returns only because passes ran out


def test_listen_defaults_to_the_latest_full_render(workspace):
    import json as _json

    from glass_harbor.cli import _latest_full_render
    from glass_harbor.paths import runs_dir

    for stamp, rng in (("20260101-000000", {"start_bar": None, "end_bar": None}),
                       ("20260102-000000", {"start_bar": 9, "end_bar": 17})):
        run = runs_dir("mix") / stamp
        run.mkdir(parents=True)
        (run / "render.json").write_text(_json.dumps({"range": rng}))
        (run / "mix.wav").write_bytes(b"")
    assert _latest_full_render("mix").name == "20260101-000000"  # the newer one is only a preview


def test_a_lock_left_by_a_dead_process_does_not_block_the_queue(workspace, monkeypatch):
    import sys

    watch.queue_path().parent.mkdir(parents=True, exist_ok=True)
    holder = subprocess.Popen([sys.executable, "-c", "import time\nfrom glass_harbor import watch\n"
                               "with watch.locked():\n    print('held', flush=True)\n    time.sleep(60)"],
                              stdout=subprocess.PIPE, text=True)
    assert holder.stdout.readline().strip() == "held"
    monkeypatch.setattr(watch, "LOCK_TIMEOUT_S", 0.2)
    with pytest.raises(TimeoutError):
        watch.add("vocal", "beat")  # a live holder blocks
    holder.kill()
    holder.wait()
    assert watch.add("vocal", "beat")["id"] == "q1"  # its death released the lock


def test_only_one_watcher_claims_a_pairing(workspace):
    item = watch.add("glock", "beat")
    assert watch._claim(item["id"], pid=1)
    assert not watch._claim(item["id"], pid=2)
    assert watch.load_queue()[0]["pid"] == 1


def test_listen_refuses_end_only_previews(tmp_path):
    from glass_harbor.listen import listen_run

    (tmp_path / "render.json").write_text(json.dumps({"range": {"start_bar": None, "end_bar": 17}}))
    with pytest.raises(ValueError, match="full renders"):
        listen_run(tmp_path, log=lambda m: None)
