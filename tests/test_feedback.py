import json
import threading
import urllib.request

import pytest

from glass_harbor import feedback, library
from glass_harbor.analyze import analyze_track
from glass_harbor.cli import main
from glass_harbor.paths import runs_dir
from glass_harbor.render import render_plan


@pytest.fixture()
def rendered(workspace, synth_files):
    paths = synth_files("a", 120, "Am", bars=16, seed=1)
    library.add_track(paths["mix"], track_id="a")
    library.save_analysis("a", analyze_track(library.load_audio("a"), beat_backend="librosa"))
    plan = {"version": 1, "title": "fb", "kind": "set", "bpm": 120, "sources": {"a": {"track": "a"}},
            "clips": [{"id": "one", "source": "a", "from_bar": 1, "bars": 8, "at_bar": 1},
                      {"id": "two", "source": "a", "from_bar": 9, "bars": 4, "at_bar": 5}]}
    run = runs_dir("fb") / "20260101-000000"
    render_plan(plan, run, mp3=False, log=lambda m: None)
    return run


def test_comment_maps_to_bars_and_clips(rendered):
    comment = feedback.add_comment(rendered, time_s=4 * 2.0 + 0.5, end_s=4 * 2.0 + 1.0, tag="vocal",
                                   text="too loud")
    assert comment["bar"] == pytest.approx(5.25, abs=0.05)
    assert set(comment["clips"]) == {"one", "two"}
    assert feedback.open_comments("fb")[0]["id"] == comment["id"]
    feedback.set_comment_status(rendered, comment["id"], "resolved", "pulled two down 3 dB")
    assert feedback.open_comments("fb") == []
    with pytest.raises(ValueError):
        feedback.add_comment(rendered, time_s=1, text="x", tag="nope")


def test_verdict_updates_taste(rendered):
    feedback.set_verdict(rendered, "fb", "approve", "love the drop")
    taste = feedback.load_taste()
    assert taste["history"][-1]["verdict"] == "approve"


def test_cli_comment_feedback_resolve_and_taste(rendered, capsys):
    assert main(["mix", "comment", "fb", "chop the hook here", "--bar", "3", "--tag", "chop", "--json"]) == 0
    comment = json.loads(capsys.readouterr().out)
    assert comment["bar"] == pytest.approx(3, abs=0.01)
    assert main(["mix", "feedback", "fb", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)[0]["text"] == "chop the hook here"
    assert main(["mix", "resolve", "fb", comment["id"]]) == 0
    capsys.readouterr()
    assert main(["taste", "set", "hiphop_blend_bars=4"]) == 0
    assert feedback.taste_default("hiphop_blend_bars") == 4
    assert main(["taste", "set", "nonsense=1"]) == 2


def test_review_server_api(rendered):
    from glass_harbor.review import serve

    server = serve("fb", port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        session = json.loads(urllib.request.urlopen(f"{base}/api/session").read())
        assert session["runs"] == [rendered.name]
        run = json.loads(urllib.request.urlopen(f"{base}/api/run/{rendered.name}").read())
        assert run["timeline"]["bars"][0]["bar"] == 1 and len(run["peaks"]) > 100
        request = urllib.request.Request(f"{base}/api/run/{rendered.name}/comments", method="POST",
                                         data=json.dumps({"time_s": 1.0, "tag": "timing", "text": "late"}).encode(),
                                         headers={"Content-Type": "application/json"})
        assert json.loads(urllib.request.urlopen(request).read())["text"] == "late"
        ranged = urllib.request.Request(f"{base}/audio/{rendered.name}", headers={"Range": "bytes=0-99"})
        response = urllib.request.urlopen(ranged)
        assert response.status == 206 and len(response.read()) == 100
        page = urllib.request.urlopen(f"{base}/").read()
        assert b"Mix Review" in page
    finally:
        server.shutdown()
        server.server_close()


def test_review_server_rejects_cross_site_requests(rendered):
    import urllib.error

    from glass_harbor.review import serve

    server = serve("fb", port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        simple = urllib.request.Request(f"{base}/api/run/{rendered.name}/comments", method="POST",
                                        data=json.dumps({"time_s": 1, "text": "x"}).encode(),
                                        headers={"Content-Type": "text/plain"})
        with pytest.raises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(simple)
        assert error.value.code == 403
        rebound = urllib.request.Request(f"{base}/api/session", headers={"Host": "evil.example:80"})
        with pytest.raises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(rebound)
        assert error.value.code == 403
    finally:
        server.shutdown()
        server.server_close()


def test_taste_set_and_add_need_values(workspace, capsys):
    assert main(["taste", "set"]) == 2
    assert main(["taste", "set", "hiphop_blend_bars"]) == 2
    assert main(["taste", "add"]) == 2
    assert feedback.load_taste()["preferences"] == []
    assert main(["taste", "set", "run_up_bars=-1"]) == 2  # a cut past the first vocal would shorten it
    assert main(["taste", "set", "run_up_bars=4"]) == 0 and feedback.taste_default("run_up_bars") == 4
