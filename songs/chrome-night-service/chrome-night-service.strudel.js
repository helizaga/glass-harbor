// @title Chrome Night Service
// @genre french house study / disco-loop filter house
// @bpm 123
// @details Pasteable song file for Strudel web. Run `glass-harbor song serve` before pasting. One-off loop-first French-house study with robotic punctuation and subtractive return design.
// @sections intro:8, groove:16, filter-open:8, breakdown:8, return:16, outro:8
// @section_roles intro:anchor, groove:groove, filter-open:lift, breakdown:breath, return:return, outro:outro

samples('http://localhost:5432')
setcpm(123 / 4)

const kickCore = s("kick_main*4")
  .n("0 1 0 1")
  .gain(1.04)

const clapCore = s("~ clap_main ~ clap_main")
  .n("0 1")
  .gain(0.5)
  .room(0.08)

const hatTight = s("hat_closed*8")
  .n("0 1 0 1 0 1 0 2")
  .gain("[0.08 0.1 0.08 0.11]*2")
  .pan(sine.range(0.42, 0.58))

const hatLift = s("hat_closed*8")
  .n("0 1 0 2 0 1 0 3")
  .gain("[0.09 0.13 0.1 0.16]*2")
  .pan(sine.range(0.34, 0.66))

const hatReturn = s("hat_closed*16")
  .n("0 0 1 0 0 2 0 3 0 0 1 0 0 2 0 4")
  .gain("[0.1 0.14 0.11 0.17]*4")
  .pan(sine.range(0.28, 0.72))

const hatOpen = s("~ hat_open ~ hat_open")
  .n("0 1")
  .gain(0.16)
  .delay("0.06:0.125:0.06")

const percWood = s("~ perc_top ~ perc_top")
  .n("0 1")
  .gain(0.15)
  .delay("0.03:0.125:0.07")

const bassGroove = note("<[d2 a1 d2 a1] [c2 g1 c2 g1] [bb1 f1 bb1 f1] [a1 e1 a1 e1]>")
  .slow(4)
  .sound("triangle,sawtooth")
  .lpf(540)
  .attack(0.01)
  .decay(0.1)
  .sustain(0.3)
  .release(0.08)
  .gain(0.36)

const bassLift = note("<[d2 a1 d2 a1] [c2 g1 c2 g1] [bb1 f1 bb1 f1] [a1 e1 a1 e1]>")
  .slow(4)
  .sound("triangle,sawtooth")
  .lpf(sine.range(620, 1080).slow(8))
  .attack(0.01)
  .decay(0.11)
  .sustain(0.32)
  .release(0.08)
  .gain(0.38)

const bassBreak = note("<[d2 ~ ~ a1] [c2 ~ ~ g1] [bb1 ~ ~ f1] [a1 ~ ~ e1]>")
  .slow(4)
  .sound("triangle")
  .lpf(260)
  .attack(0.02)
  .decay(0.12)
  .sustain(0.14)
  .release(0.14)
  .gain(0.1)

const bassReturn = note("<[d2 a1 d2 f2] [c2 g1 c2 e2] [bb1 f1 bb1 d2] [a1 e1 a1 c2]>")
  .slow(4)
  .sound("triangle,sawtooth")
  .lpf(920)
  .attack(0.01)
  .decay(0.11)
  .sustain(0.38)
  .release(0.08)
  .gain(0.46)

const chordPulse = note("<[d4 f4 a4 c5] [c4 e4 g4 bb4] [bb3 d4 f4 a4] [a3 c4 e4 g4]>")
  .slow(4)
  .sound("square,sawtooth")
  .attack(0.01)
  .decay(0.12)
  .sustain(0.06)
  .release(0.1)
  .gain(0.12)
  .delay("0.08:0.125:0.08")

const chordIntro = chordPulse
  .lpf(760)
  .gain(0.08)

const chordGroove = chordPulse
  .lpf(sine.range(980, 1800).slow(16))
  .gain(0.12)

const chordOpen = chordPulse
  .lpf(sine.range(1500, 3200).slow(8))
  .gain(0.16)

const chordBreak = chordPulse
  .lpf(540)
  .gain(0.04)

const chordReturn = chordPulse
  .lpf(2500)
  .gain(0.18)

const robotHook = note("<[a4 ~ c5 ~ a4 ~ d5 ~] [g4 ~ bb4 ~ g4 ~ c5 ~] [f4 ~ a4 ~ f4 ~ bb4 ~] [e4 ~ g4 ~ e4 ~ a4 ~]>")
  .slow(4)
  .sound("sawtooth,square")
  .vowel("<i e a o>")
  .lpf(sine.range(980, 2200).slow(8))
  .attack(0.03)
  .decay(0.11)
  .sustain(0.16)
  .release(0.08)
  .delay("0.12:0.125:0.1")
  .room(0.12)
  .gain(0.08)

const chopPunct = s("vocal_chop*8")
  .n("0 1 0 2 0 1 0 3")
  .gain("[0.03 0.06 0.04 0.08]*2")
  .pan(sine.range(0.4, 0.6))

const airBed = s("air_texture")
  .slow(8)
  .gain(0.12)
  .room(0.82)
  .lpf(sine.range(720, 1800).slow(10))

const shimmer = s("shimmer_fx")
  .slow(8)
  .gain(0.05)

const impact = s("impact_wide ~ ~ ~")
  .slow(4)
  .gain(0.26)

stack(
  arrange(
    [8, kickCore.gain(0.9)],
    [16, kickCore],
    [8, kickCore.gain(0.98)],
    [8, silence],
    [16, kickCore.gain(1.04)],
    [8, kickCore.gain(0.54)]
  ),

  arrange(
    [8, silence],
    [16, clapCore],
    [8, clapCore.gain(0.34)],
    [8, silence],
    [16, clapCore.gain(0.6)],
    [8, silence]
  ),

  arrange(
    [8, hatTight.gain(0.46)],
    [16, hatTight],
    [8, hatLift.gain(0.84)],
    [8, silence],
    [16, hatReturn.gain(0.9)],
    [8, hatTight.gain(0.34)]
  ),

  arrange(
    [8, silence],
    [16, silence],
    [8, hatOpen.gain(0.08)],
    [8, silence],
    [16, hatOpen.gain(0.18)],
    [8, silence]
  ),

  arrange(
    [8, silence],
    [16, percWood.gain(0.12)],
    [8, percWood.gain(0.16)],
    [8, silence],
    [16, percWood.gain(0.18)],
    [8, silence]
  ),

  arrange(
    [8, silence],
    [16, bassGroove],
    [8, bassLift],
    [8, bassBreak],
    [16, bassReturn.gain(1.02)],
    [8, silence]
  ),

  arrange(
    [8, chordIntro],
    [16, chordGroove],
    [8, chordOpen],
    [8, chordBreak],
    [16, chordReturn],
    [8, chordIntro.gain(0.6)]
  ),

  arrange(
    [8, silence],
    [16, silence],
    [8, silence],
    [8, chopPunct.gain(0.08)],
    [16, robotHook.gain(1.08)],
    [8, silence]
  ),

  arrange(
    [8, airBed.gain(1.02)],
    [16, airBed.gain(0.08)],
    [8, shimmer.gain(0.06)],
    [8, airBed.gain(0.14)],
    [16, airBed.gain(0.08)],
    [8, airBed.gain(0.08)]
  ),

  arrange(
    [8, silence],
    [16, silence],
    [8, silence],
    [8, silence],
    [16, impact],
    [8, silence]
  )
)
