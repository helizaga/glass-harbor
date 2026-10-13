"""Word timings from the published lyrics: CTC forced alignment (torchaudio's MMS aligner) of the synced text (the
file's own tags or LRCLIB) to the acapella, with Whisper kept where the published text has nothing (spoken intros,
ad-libs).

Whisper's word starts are coarse on rap. On Kodak Black's "Thankful" it heard 308 of the 430 published words and put
their starts a median 122 ms early: 79 ms from the nearest vocal onset against 41 ms for the aligned starts, which
sit on a 1.7x energy rise where Whisper's sit on none. Aligning the known text also times the words Whisper misheard.
The aligner cannot tell the right lyrics from another song's (mean score 0.20 vs 0.16), so the gate is whether
Whisper heard most of the published words. The MMS aligner weights are CC-BY-NC 4.0 (non-commercial use).
"""

from __future__ import annotations

import difflib
import json
import re
from typing import Any, Callable

import numpy as np

from glass_harbor import audio as A
from glass_harbor import library

Log = Callable[[str], None]

MIN_AGREEMENT = 0.5  # share of the published words Whisper also heard; below it the text may be another version
CHUNK_S = 20.0  # the aligner's model runs on 20 s pieces (memory); each line is then aligned in its own window
MARGIN_S = 0.25  # Whisper words this close to an aligned line belong to it
WINDOW_PAD_S = 1.0  # each line is searched for this far around where it was heard (or its published timestamp)
NEIGHBOUR_S = 0.15  # ...but no further than this into where Whisper heard the next or previous line
MAX_OFFSET_S = 0.5  # aligned starts further than this from Whisper's (median) mean the alignment went wrong
MIN_LINE_SHARE = 0.8  # fewer published lines than this aligned: the text and the recording disagree, keep Whisper


def _token(word: str) -> str:
    """The aligner's alphabet: lowercase letters and apostrophes."""
    return re.sub(r"[^a-z']", "", word.lower()).strip("'")


def _published(lines: list[dict[str, Any]]) -> list[tuple[int, str, str]]:
    """(line index, word as written, aligner token) for every word of the published text."""
    return [(index, raw, _token(raw)) for index, line in enumerate(lines) for raw in line["text"].split() if _token(raw)]


def _heard(segments: list[dict[str, Any]]) -> list[tuple[str, float, float]]:
    return [(_token(w["word"]), float(w["start"]), float(w["end"])) for seg in segments for w in seg["words"]
            if _token(w["word"])]


def _matches(published: list[tuple[int, str, str]], heard: list[tuple[str, float, float]]) -> list[tuple[int, int]]:
    """(published index, heard index) of the words Whisper heard, in order."""
    matcher = difflib.SequenceMatcher(None, [p[2] for p in published], [h[0] for h in heard], autojunk=False)
    return [(block.a + k, block.b + k) for block in matcher.get_matching_blocks() for k in range(block.size)]


def text_agreement(lines: list[dict[str, Any]], segments: list[dict[str, Any]]) -> float:
    """Share of the published words that Whisper heard, in order."""
    published = _published(lines)
    if not published:
        return 0.0
    return len(_matches(published, _heard(segments))) / len(published)


def line_windows(lines: list[dict[str, Any]], segments: list[dict[str, Any]], duration: float
                 ) -> list[tuple[float, float]]:
    """Where to look for each published line (s): around the words of it Whisper heard, else between its published
    timestamp and the next line's. One song-wide alignment let Thankful's first line drift into the spoken intro
    (which also says "I'm thankful"); a window per line keeps every line near where it was actually sung."""
    published, heard = _published(lines), _heard(segments)
    found: dict[int, list[tuple[float, float]]] = {}
    for p, h in _matches(published, heard):
        found.setdefault(published[p][0], []).append(heard[h][1:])
    windows = []
    for index, line in enumerate(lines):
        if index in found:
            a, b = found[index][0][0], found[index][-1][1]
        else:
            a = float(line.get("time", 0.0))
            b = float(lines[index + 1]["time"]) if index + 1 < len(lines) and "time" in lines[index + 1] else a + 6.0
        lo, hi = max(0.0, a - WINDOW_PAD_S), min(duration, b + WINDOW_PAD_S)
        # Never into where Whisper heard the neighbouring lines (its starts run early, hence the small allowance).
        before = [found[i][-1][1] for i in found if i < index]
        after = [found[i][0][0] for i in found if i > index]
        if before:
            lo = max(lo, min(a, max(before) - NEIGHBOUR_S))
        if after:
            hi = min(hi, max(b, min(after) + NEIGHBOUR_S))
        windows.append((lo, hi))
    return windows


def align_lines(vocal: np.ndarray, lines: list[dict[str, Any]], windows: list[tuple[float, float]]
                ) -> list[dict[str, Any]]:
    """Each published line with its words timed (s) on the acapella, aligned inside its own window with a wildcard
    on both sides to absorb the neighbouring lines' audio."""
    import soxr
    import torch
    import torchaudio

    bundle = torchaudio.pipelines.MMS_FA
    model = bundle.get_model(with_star=True).eval()
    tokenizer, aligner = bundle.get_tokenizer(), bundle.get_aligner()
    wave = torch.from_numpy(soxr.resample(A.mono(vocal), A.SR, bundle.sample_rate).astype(np.float32))[None]
    size = int(CHUNK_S * bundle.sample_rate)
    starts = list(range(0, wave.shape[1], size))
    if len(starts) > 1 and wave.shape[1] - starts[-1] < bundle.sample_rate:
        starts.pop()  # a sliver too short for the model joins the piece before it
    bounds = list(zip(starts, starts[1:] + [wave.shape[1]]))
    with torch.inference_mode():
        emission = torch.cat([model(wave[:, a:b])[0] for a, b in bounds], dim=1)[0]
    frame_s = wave.shape[1] / emission.shape[0] / bundle.sample_rate

    out = []
    for index, (line, (a, b)) in enumerate(zip(lines, windows)):
        raws = [raw for raw in line["text"].split() if _token(raw)]
        if not raws:
            continue
        targets = tokenizer(["*"] + [_token(raw) for raw in raws] + ["*"])
        lo, hi = int(a / frame_s), min(emission.shape[0], int(b / frame_s) + 1)
        # CTC needs a frame per letter, plus a blank between repeated letters.
        needed = sum(len(word) + sum(x == y for x, y in zip(word, word[1:])) for word in targets)
        if hi - lo < needed:
            continue  # the window cannot hold the line: Whisper's timings stay for it
        try:
            spans = aligner(emission[lo:hi], targets)[1:-1]
        except RuntimeError:
            continue
        out.append({"index": index, "text": line["text"], "words": [
            {"word": raw.strip(",.!?;:\"()"), "start": round((lo + span[0].start) * frame_s, 3),
             "end": round((lo + span[-1].end) * frame_s, 3), "prob": round(float(np.mean([t.score for t in span])), 3)}
            for raw, span in zip(raws, spans)]})
    return out


def timing_offset(aligned: list[dict[str, Any]], segments: list[dict[str, Any]]) -> float:
    """Median |aligned start - Whisper start| (s) over the words both have; Whisper runs about 0.12 s early on rap."""
    mine = [(_token(w["word"]), w["start"]) for line in aligned for w in line["words"] if _token(w["word"])]
    heard = _heard(segments)
    matcher = difflib.SequenceMatcher(None, [m[0] for m in mine], [h[0] for h in heard], autojunk=False)
    gaps = [abs(mine[block.a + k][1] - heard[block.b + k][1])
            for block in matcher.get_matching_blocks() for k in range(block.size)]
    return float(np.median(gaps)) if gaps else float("inf")  # nothing to check against: not trusted


def merge(whisper: dict[str, Any], aligned: list[dict[str, Any]], skipped: list[int] | None = None) -> dict[str, Any]:
    """Aligned lines as segments, plus the Whisper words that fall outside every aligned line (so a published line the
    aligner skipped keeps whatever Whisper heard of it). ``skipped`` records those lines' indexes."""
    spans = [(line["words"][0]["start"] - MARGIN_S, line["words"][-1]["end"] + MARGIN_S) for line in aligned]
    segments = [{"start": line["words"][0]["start"], "end": line["words"][-1]["end"], "text": line["text"],
                 "words": line["words"]} for line in aligned]
    for seg in whisper["segments"]:
        kept = [w for w in seg["words"] if not any(a <= (w["start"] + w["end"]) / 2 <= b for a, b in spans)]
        if kept:
            segments.append({"start": kept[0]["start"], "end": kept[-1]["end"],
                             "text": " ".join(w["word"] for w in kept), "words": kept})
    segments.sort(key=lambda s: s["start"])
    return {**whisper, "segments": segments, "timing": "aligned", "aligned_lines": len(aligned),
            "skipped_lines": skipped or []}


def whisper_path(track_id: str):
    return library.track_dir(track_id) / "lyrics_whisper.json"


def align_track(track_id: str, *, log: Log = print) -> dict[str, Any] | None:
    """Re-time the track's lyrics from its published text. Returns the merged lyrics (also written to lyrics.json,
    with Whisper's own output kept in lyrics_whisper.json), or None when Whisper stays (no text, no acapella, the
    text disagrees with what was sung, or no aligner installed)."""
    from glass_harbor.lyrics import load_lyrics, lyrics_path
    from glass_harbor.lyrics_ref import load_reference

    reference, current = load_reference(track_id), load_lyrics(track_id)
    if not reference or not reference.get("lines") or not current:
        return None
    if "vocals" not in library.available_stems(track_id):
        return None
    saved = whisper_path(track_id)
    whisper = json.loads(saved.read_text()) if current.get("timing") == "aligned" and saved.exists() else current
    agreement = text_agreement(reference["lines"], whisper["segments"])
    if agreement < MIN_AGREEMENT:
        log(f"kept Whisper's timings for {track_id}: it heard only {agreement:.0%} of the published words "
            "(another version of the song?)")
        return None
    vocal = library.load_audio(track_id, "vocals")
    windows = line_windows(reference["lines"], whisper["segments"], vocal.shape[0] / A.SR)
    try:
        aligned = align_lines(vocal, reference["lines"], windows)
    except ImportError:
        log("word alignment needs torch and torchaudio (pip install -e '.[ml]'); kept Whisper's timings")
        return None
    except OSError as error:  # the first run downloads the aligner's model; offline, Whisper's timings stay
        log(f"could not load the word aligner ({error.__class__.__name__}); kept Whisper's timings")
        return None
    alignable = [i for i, line in enumerate(reference["lines"]) if any(_token(w) for w in line["text"].split())]
    done = {line["index"] for line in aligned}
    skipped = [i for i in alignable if i not in done]
    if not aligned or len(done) < MIN_LINE_SHARE * len(alignable):
        log(f"kept Whisper's timings for {track_id}: only {len(done)} of {len(alignable)} published lines aligned")
        return None
    offset = timing_offset(aligned, whisper["segments"])
    if offset > MAX_OFFSET_S:
        log(f"kept Whisper's timings for {track_id}: the aligned words land {offset:.2f} s from where Whisper heard them")
        return None
    saved.write_text(json.dumps(whisper, indent=1) + "\n")
    merged = merge(whisper, aligned, skipped)
    lyrics_path(track_id).write_text(json.dumps(merged, indent=1) + "\n")
    timed = sum(len(line["words"]) for line in aligned)
    log(f"timed {timed} published words on {track_id}'s acapella (Whisper heard {agreement:.0%} of them)"
        + (f"; {len(skipped)} line(s) keep Whisper's timing" if skipped else ""))
    return merged
