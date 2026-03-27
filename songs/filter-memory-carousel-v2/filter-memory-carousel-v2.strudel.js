// @title Filter Memory Carousel Variant 2
// @genre french house study / disco-touch loop house
// @bpm 122
// @details Pasteable song file for Strudel web. Run `glass-harbor song serve` before pasting. Variant scaffold 2 explores deeper subtraction and a more withheld return.
// @sections intro:8, groove:16, lift:8, breakdown:8, drop:16, outro:8

samples('http://localhost:5432')
setcpm(122 / 4)

const kick = s("kick_main*4")
  .n("0 1 0 1")
  .gain(1.02)

const clap = s("~ clap_main ~ clap_main")
  .n("0 1")
  .gain(0.46)
  .room(0.1)

const hatsGroove = s("hat_closed*8")
  .n("0 1 0 2 0 1 0 3")
  .gain("[0.07 0.1 0.08 0.12]*2")
  .pan(sine.range(0.42, 0.58))

const hatsLift = s("hat_closed*8")
  .n("0 1 0 2 0 1 0 4")
  .gain("[0.1 0.14 0.11 0.18]*2")
  .pan(sine.range(0.36, 0.64))

const hatsDrop = s("hat_closed*16")
  .n("0 0 1 0 0 2 0 3 0 0 1 0 0 2 0 4")
  .gain("[0.11 0.16 0.12 0.19]*4")
  .pan(sine.range(0.3, 0.7))

const openHat = s("~ hat_open ~ hat_open")
  .n("0 1")
  .gain(0.16)
  .delay("0.08:0.125:0.06")

const percSnap = s("~ perc_top ~ perc_top")
  .n("0 1")
  .gain(0.14)
  .delay("0.06:0.125:0.08")

const bassGroove = note("<[d2 a1 d2 a1] [c2 g1 c2 g1] [bb1 f1 bb1 f1] [a1 e1 a1 e1]>")
  .slow(4)
  .sound("triangle,sawtooth")
  .lpf(520)
  .attack(0.01)
  .decay(0.1)
  .sustain(0.32)
  .release(0.08)
  .gain(0.34)

const bassLift = note("<[d2 a1 d2 a1] [c2 g1 c2 g1] [bb1 f1 bb1 f1] [a1 e1 a1 e1]>")
  .slow(4)
  .sound("triangle,sawtooth")
  .lpf(sine.range(540, 940).slow(8))
  .attack(0.01)
  .decay(0.12)
  .sustain(0.34)
  .release(0.08)
  .gain(0.38)

const bassBreak = note("<[d2 ~ ~ a1] [c2 ~ ~ g1] [bb1 ~ ~ f1] [a1 ~ ~ e1]>")
  .slow(4)
  .sound("triangle")
  .lpf(300)
  .attack(0.02)
  .decay(0.12)
  .sustain(0.18)
  .release(0.18)
  .gain(0.12)

const bassDrop = note("<[d2 a1 d2 f2] [c2 g1 c2 e2] [bb1 f1 bb1 d2] [a1 e1 a1 c2]>")
  .slow(4)
  .sound("triangle,sawtooth")
  .lpf(900)
  .attack(0.01)
  .decay(0.12)
  .sustain(0.4)
  .release(0.08)
  .gain(0.48)

const padDust = note("<[d4 f4 a4 c5] [c4 e4 g4 bb4] [bb3 d4 f4 a4] [a3 c4 e4 g4]>")
  .slow(4)
  .sound("sawtooth")
  .attack(0.2)
  .decay(0.18)
  .sustain(0.5)
  .release(0.32)
  .room(0.5)
  .delay("0.12:0.125:0.16")

const padIntro = padDust
  .lpf(640)
  .gain(0.08)

const padGroove = padDust
  .lpf(sine.range(760, 1500).slow(16))
  .gain(0.12)

const padLift = padDust
  .lpf(sine.range(980, 2400).slow(8))
  .gain(0.16)

const padBreak = padDust
  .lpf(560)
  .gain(0.06)

const pluckLoop = note("<[~ a4 ~ c5 ~ a4 ~ d5] [~ g4 ~ bb4 ~ g4 ~ c5] [~ f4 ~ a4 ~ f4 ~ bb4] [~ e4 ~ g4 ~ e4 ~ a4]>")
  .slow(4)
  .sound("triangle")
  .lpf(1320)
  .attack(0.01)
  .decay(0.1)
  .sustain(0.04)
  .release(0.08)
  .delay("0.18:0.125:0.16")
  .room(0.16)
  .gain(0.07)

const hookRobot = note("<[d5 ~ c5 ~ a4 ~ c5 ~] [c5 ~ bb4 ~ g4 ~ bb4 ~] [bb4 ~ a4 ~ f4 ~ a4 ~] [a4 ~ g4 ~ e4 ~ g4 ~]>")
  .slow(4)
  .sound("sawtooth,square")
  .vowel("<i e a o>")
  .lpf(sine.range(820, 1900).slow(8))
  .attack(0.03)
  .decay(0.12)
  .sustain(0.18)
  .release(0.08)
  .delay("0.12:0.125:0.1")
  .room(0.12)
  .gain(0.09)

const robotAnswer = s("vocal_chop*8")
  .n("0 1 0 2 0 1 0 3")
  .gain("[0.03 0.07 0.04 0.08]*2")
  .pan(sine.range(0.38, 0.62))

const air = s("air_texture")
  .slow(8)
  .gain(0.14)
  .room(0.9)
  .lpf(sine.range(700, 2200).slow(12))

const shimmer = s("shimmer_fx")
  .slow(8)
  .gain(0.08)

const riser = s("riser_up")
  .slow(8)
  .gain(0.08)

const impact = s("impact_wide ~ ~ ~")
  .slow(4)
  .gain(0.32)

stack(
  arrange(
    [8, kick.gain(0.92)],
    [16, kick],
    [8, kick.gain(0.96)],
    [8, silence],
    [16, kick.gain(1.02)],
    [8, kick.gain(0.54)]
  ),

  arrange(
    [8, silence],
    [16, clap],
    [8, silence],
    [8, silence],
    [16, clap.gain(0.6)],
    [8, silence]
  ),

  arrange(
    [8, hatsGroove.gain(0.5)],
    [16, hatsGroove],
    [8, hatsLift.gain(0.82)],
    [8, silence],
    [16, hatsDrop.gain(0.92)],
    [8, hatsGroove.gain(0.4)]
  ),

  arrange(
    [8, silence],
    [16, silence],
    [8, openHat.gain(0.08)],
    [8, silence],
    [16, openHat.gain(0.18)],
    [8, silence]
  ),

  arrange(
    [8, silence],
    [16, percSnap.gain(0.12)],
    [8, silence],
    [8, silence],
    [16, percSnap.gain(0.16)],
    [8, silence]
  ),

  arrange(
    [8, silence],
    [16, bassGroove],
    [8, bassLift.gain(0.92)],
    [8, bassBreak],
    [16, bassDrop.gain(1.08)],
    [8, silence]
  ),

  arrange(
    [8, padIntro],
    [16, padGroove],
    [8, padLift.gain(0.88)],
    [8, padBreak.gain(0.82)],
    [16, padLift.gain(0.96)],
    [8, padIntro]
  ),

  arrange(
    [8, silence],
    [16, pluckLoop],
    [8, silence],
    [8, silence],
    [16, pluckLoop.gain(0.06)],
    [8, silence]
  ),

  arrange(
    [8, silence],
    [16, silence],
    [8, silence],
    [8, robotAnswer.gain(0.08)],
    [16, hookRobot.gain(1.06)],
    [8, silence]
  ),

  arrange(
    [8, air.gain(1.08)],
    [16, air.gain(0.1)],
    [8, shimmer.gain(0.06)],
    [8, air.gain(0.18)],
    [16, air.gain(0.08)],
    [8, air.gain(0.08)]
  ),

  arrange(
    [8, silence],
    [16, silence],
    [8, riser],
    [8, silence],
    [16, impact],
    [8, silence]
  )
)
