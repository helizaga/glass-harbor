// @title Signal Lanterns
// @genre cinematic indie electronica / festival-lift electronic
// @bpm 105
// @details Pasteable song file for Strudel web. Run `glass-harbor song serve` before pasting.
// @sections intro:8, groove:16, lift:8, breakdown:16, return:16, outro:8
// @section_roles intro:anchor, groove:groove, lift:lift, breakdown:breath, return:return, outro:outro

samples('http://localhost:5432')
setcpm(105 / 4)

const kick = s("kick_main*4")
  .n("0 1 0 1")
  .gain(1.02)

const clap = s("~ clap_main ~ clap_main")
  .n("0 1")
  .gain(0.48)
  .room(0.12)

const clapReturn = clap
  .delay("0.12:0.125:0.08")
  .gain(0.58)

const hatsGroove = s("hat_closed*8")
  .n("0 1 0 2 0 1 0 3")
  .gain("[0.06 0.09 0.07 0.11]*2")
  .pan(sine.range(0.38, 0.62))

const hatsLift = s("hat_closed*8")
  .n("0 1 0 2 0 1 0 4")
  .gain("[0.09 0.13 0.1 0.16]*2")
  .pan(sine.range(0.34, 0.66))

const hatsReturn = s("hat_closed*16")
  .n("0 0 1 0 0 2 0 3 0 0 1 0 0 2 0 4")
  .gain("[0.1 0.14 0.11 0.18]*4")
  .pan(sine.range(0.28, 0.72))

const openHat = s("~ hat_open ~ hat_open")
  .n("0 1")
  .gain(0.18)
  .delay("0.08:0.125:0.06")

const percMarch = s("perc_top*8")
  .n("0 1 0 2 0 1 0 3")
  .gain("[0.08 0.11 0.09 0.12]*2")
  .delay("0.04:0.125:0.08")

const percLift = s("perc_top*8")
  .n("0 1 2 1 0 1 3 1")
  .gain("[0.09 0.13 0.1 0.15]*2")
  .delay("0.06:0.125:0.1")

const bassGroove = note("<[d2 ~ a1 ~] [b1 ~ fs1 ~] [g1 ~ d2 ~] [a1 ~ e2 ~]>")
  .slow(4)
  .sound("triangle,sawtooth")
  .lpf(620)
  .attack(0.01)
  .decay(0.14)
  .sustain(0.34)
  .release(0.12)
  .gain(0.28)

const bassPulse = note("<[d2 a1 ~ a1] [b1 fs1 ~ fs1] [g1 d2 ~ d2] [a1 e2 ~ e2]>")
  .slow(4)
  .sound("triangle,sawtooth")
  .lpf(sine.range(680, 980).slow(8))
  .attack(0.01)
  .decay(0.12)
  .sustain(0.32)
  .release(0.1)
  .gain(0.34)

const bassBreak = note("<[d2 ~ ~ ~] [b1 ~ ~ ~] [g1 ~ ~ ~] [a1 ~ ~ ~]>")
  .slow(4)
  .sound("triangle")
  .lpf(320)
  .attack(0.02)
  .decay(0.12)
  .sustain(0.18)
  .release(0.24)
  .gain(0.12)

const bassReturn = note("<[d2 a1 d2 a1] [b1 fs1 b1 fs1] [g1 d2 g1 d2] [a1 e2 a1 e2]>")
  .slow(4)
  .sound("triangle,sawtooth")
  .lpf(1100)
  .attack(0.01)
  .decay(0.14)
  .sustain(0.38)
  .release(0.08)
  .gain(0.42)

const padCore = note("<[d4 fs4 a4 e5] [b3 d4 fs4 a4] [g3 b3 d4 a4] [a3 cs4 e4 b4]>")
  .slow(4)
  .sound("sawtooth")
  .attack(0.4)
  .decay(0.18)
  .sustain(0.86)
  .release(1.2)
  .room(0.94)
  .delay("0.22:0.25:0.26")

const padIntro = padCore
  .lpf(880)
  .gain(0.08)

const padGroove = padCore
  .lpf(sine.range(1100, 2200).slow(16))
  .gain(0.12)

const padBreak = padCore
  .lpf(sine.range(900, 2600).slow(10))
  .gain(0.18)

const hookGlow = note("<[a4 ~ fs4 ~ e4 ~ fs4 ~] [fs4 ~ d4 ~ cs4 ~ d4 ~] [d4 ~ b3 ~ a3 ~ b3 ~] [e4 ~ cs4 ~ b3 ~ cs4 ~]>")
  .slow(4)
  .sound("triangle,sawtooth")
  .lpf(sine.range(1200, 2400).slow(12))
  .attack(0.03)
  .decay(0.16)
  .sustain(0.22)
  .release(0.22)
  .delay("0.16:0.125:0.16")
  .room(0.18)
  .gain(0.11)

const hookReturn = note("<[a4 fs4 ~ e4 ~ fs4 a4 ~] [fs4 d4 ~ cs4 ~ d4 fs4 ~] [d4 b3 ~ a3 ~ b3 d4 ~] [e4 cs4 ~ b3 ~ cs4 e4 ~]>")
  .slow(4)
  .sound("sawtooth")
  .vowel("<a e i o>")
  .lpf(sine.range(1800, 3400).slow(8))
  .attack(0.02)
  .decay(0.14)
  .sustain(0.26)
  .release(0.14)
  .delay("0.12:0.125:0.14")
  .room(0.2)
  .gain(0.16)

const vocalMist = s("vocal_chop*8")
  .n("0 1 0 2 0 1 0 3")
  .gain("[0.03 0.06 0.04 0.08]*2")
  .pan(sine.range(0.36, 0.64))
  .delay("0.18:0.125:0.1")

const vocalLift = s("vocal_chop*8")
  .n("0 1 2 1 0 1 3 1")
  .gain("[0.05 0.09 0.06 0.11]*2")
  .pan(sine.range(0.3, 0.7))
  .delay("0.16:0.125:0.12")

const air = s("air_texture")
  .slow(8)
  .gain(0.16)
  .room(1)
  .lpf(sine.range(700, 2600).slow(10))

const shimmer = s("shimmer_fx")
  .slow(8)
  .gain(0.1)

const riser = s("riser_up")
  .slow(8)
  .gain(0.16)
  .room(0.98)

const impact = s("impact_wide ~ ~ ~")
  .slow(4)
  .gain(0.34)

stack(
  arrange(
    [8, kick.gain(0.78)],
    [16, kick],
    [8, kick.gain(0.9)],
    [16, silence],
    [16, kick.gain(1.02)],
    [8, kick.gain(0.48)]
  ),

  arrange(
    [8, silence],
    [16, clap],
    [8, clap.gain(0.18)],
    [16, silence],
    [16, clapReturn],
    [8, silence]
  ),

  arrange(
    [8, hatsGroove.gain(0.35)],
    [16, hatsGroove],
    [8, hatsLift],
    [16, silence],
    [16, hatsReturn],
    [8, hatsGroove.gain(0.3)]
  ),

  arrange(
    [8, silence],
    [16, silence],
    [8, openHat.gain(0.08)],
    [16, silence],
    [16, openHat],
    [8, silence]
  ),

  arrange(
    [8, silence],
    [16, percMarch.gain(0.72)],
    [8, percLift],
    [16, silence],
    [16, percMarch.gain(1.02)],
    [8, silence]
  ),

  arrange(
    [8, silence],
    [16, bassGroove],
    [8, bassPulse],
    [16, bassBreak],
    [16, bassReturn],
    [8, silence]
  ),

  arrange(
    [8, padIntro],
    [16, padGroove],
    [8, padGroove.gain(0.14)],
    [16, padBreak],
    [16, padBreak.gain(0.88)],
    [8, padIntro]
  ),

  arrange(
    [8, silence],
    [16, hookGlow.gain(0.72)],
    [8, hookGlow],
    [16, silence],
    [16, hookReturn],
    [8, silence]
  ),

  arrange(
    [8, vocalMist.gain(0.6)],
    [16, vocalMist],
    [8, vocalLift],
    [16, vocalMist.gain(0.52)],
    [16, vocalLift.gain(1.02)],
    [8, vocalMist.gain(0.36)]
  ),

  arrange(
    [8, air],
    [16, air.gain(0.14)],
    [8, shimmer.gain(0.08)],
    [16, air.gain(0.18)],
    [16, shimmer.gain(0.12)],
    [8, air.gain(0.1)]
  ),

  arrange(
    [8, silence],
    [16, silence],
    [8, riser.gain(0.12)],
    [16, riser],
    [16, silence],
    [8, silence]
  ),

  arrange(
    [8, silence],
    [16, silence],
    [8, silence],
    [16, silence],
    [16, impact],
    [8, silence]
  )
)
