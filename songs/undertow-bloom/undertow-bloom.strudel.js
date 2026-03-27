// @title Undertow Bloom
// @genre emotional progressive house / melodic electronica
// @bpm 121
// @details Pasteable song file for Strudel web. Run `glass-harbor song serve` before pasting.
// @sections intro:16, pulse:16, lift:8, breakdown:16, bloom:16, release:16, outro:8

samples('http://localhost:5432')
setcpm(121 / 4)

const kick = s("kick_main*4")
  .n("0 1 0 1")
  .gain(1.04)

const clap = s("~ clap_main ~ clap_main")
  .n("0 1")
  .gain(0.52)
  .room(0.12)

const clapBloom = clap
  .delay("0.16:0.125:0.1")
  .gain(0.66)

const hatsPulse = s("hat_closed*8")
  .n("0 1 0 2 0 1 0 3")
  .gain("[0.06 0.08 0.06 0.1]*2")
  .pan(sine.range(0.42, 0.58))

const hatsLift = s("hat_closed*8")
  .n("0 1 0 2 0 1 0 4")
  .gain("[0.08 0.11 0.08 0.14]*2")
  .pan(sine.range(0.36, 0.64))

const hatsBloom = s("hat_closed*16")
  .n("0 0 1 0 0 2 0 3 0 0 1 0 0 2 0 4")
  .gain("[0.1 0.14 0.11 0.17]*4")
  .pan(sine.range(0.3, 0.7))

const openHat = s("~ hat_open ~ hat_open")
  .n("0 1")
  .gain(0.22)
  .delay("0.1:0.125:0.08")

const percTop = s("~ perc_top ~ perc_top")
  .n("0 1")
  .gain(0.24)
  .delay("0.08:0.125:0.12")

const bassPulse = note("<[d1 ~ a1 ~] [bb0 ~ f1 ~] [f1 ~ c2 ~] [c1 ~ g1 ~]>")
  .slow(4)
  .sound("triangle")
  .lpf(520)
  .attack(0.02)
  .decay(0.12)
  .sustain(0.38)
  .release(0.2)
  .gain(0.26)

const bassGhost = note("<[d1 ~ ~ ~] [bb0 ~ ~ ~] [f1 ~ ~ ~] [c1 ~ ~ ~]>")
  .slow(4)
  .sound("triangle")
  .lpf(380)
  .attack(0.03)
  .decay(0.12)
  .sustain(0.24)
  .release(0.3)
  .gain(0.12)

const bassBloom = note("<[d1 ~ a1 d2] [bb0 ~ f1 bb1] [f1 ~ c2 f1] [c1 ~ g1 c2]>")
  .slow(4)
  .sound("sawtooth,triangle")
  .lpf(860)
  .attack(0.01)
  .decay(0.12)
  .sustain(0.52)
  .release(0.12)
  .gain(0.64)

const padBase = note("<[d3,f3,a3,c4,e4] [bb2,d3,f3,a3,c4] [f3,a3,c4,e4,g4] [c3,e3,g3,bb3,d4]>")
  .slow(4)
  .sound("sawtooth")
  .attack(0.56)
  .decay(0.2)
  .sustain(0.94)
  .release(1.6)
  .room(0.96)
  .delay("0.22:0.25:0.3")

const padIntro = padBase
  .lpf(760)
  .gain(0.09)

const padPulse = padBase
  .lpf(sine.range(920, 1800).slow(16))
  .gain(0.13)

const padBreak = padBase
  .lpf(sine.range(1200, 3000).slow(12))
  .gain(0.18)

const pulsePluck = note("<[~ ~ a4 ~ ~ ~ c5 ~] [~ ~ f4 ~ ~ ~ a4 ~] [~ ~ c5 ~ ~ ~ e5 ~] [~ ~ g4 ~ ~ ~ bb4 ~]>")
  .slow(4)
  .sound("triangle")
  .lpf(1500)
  .attack(0.01)
  .decay(0.12)
  .sustain(0.06)
  .release(0.1)
  .delay("0.22:0.125:0.18")
  .room(0.22)
  .gain(0.04)

const hookBreak = note("<[a4 ~ c5 ~ d5 ~ c5 ~] [f4 ~ a4 ~ c5 ~ a4 ~] [c5 ~ e5 ~ f5 ~ e5 ~] [g4 ~ bb4 ~ a4 ~ g4 ~]>")
  .slow(4)
  .sound("sawtooth")
  .vowel("<a e i o>")
  .lpf(1680)
  .attack(0.16)
  .decay(0.18)
  .sustain(0.44)
  .release(0.9)
  .delay("0.52:0.125:0.58")
  .room(0.9)
  .gain(0.11)

const hookBloom = note("<[a4 c5 ~ d5 ~ c5 a4 ~] [f4 a4 ~ c5 ~ a4 f4 ~] [c5 e5 ~ f5 ~ e5 c5 ~] [g4 bb4 ~ a4 ~ g4 f4 ~]>")
  .slow(4)
  .sound("sawtooth")
  .vowel("<a e o i>")
  .lpf(2460)
  .attack(0.04)
  .decay(0.14)
  .sustain(0.36)
  .release(0.24)
  .delay("0.18:0.125:0.14")
  .room(0.22)
  .gain(0.18)

const arpBloom = note("<[d5 a5 c6 a5 f5 a5 c6 a5] [bb4 f5 a5 f5 d5 f5 a5 f5] [f5 c6 e6 c6 a5 c6 e6 c6] [c5 g5 bb5 g5 e5 g5 bb5 g5]>")
  .slow(4)
  .sound("triangle")
  .lpf(saw.range(1100, 2300).slow(8))
  .attack(0.01)
  .decay(0.1)
  .sustain(0.16)
  .release(0.08)
  .delay("0.18:0.125:0.16")
  .room(0.2)
  .gain(0.09)

const air = s("air_texture")
  .slow(8)
  .gain(0.16)
  .room(1)
  .lpf(sine.range(650, 2400).slow(10))

const shimmer = s("shimmer_fx")
  .slow(8)
  .gain(0.11)

const riser = s("riser_up")
  .slow(8)
  .gain(0.2)
  .room(0.98)

const vocal = s("vocal_chop")
  .delay("0.18:0.25:0.12")
  .gain(0.09)

const impact = s("impact_wide ~ ~ ~")
  .slow(4)
  .gain(0.4)

stack(
  arrange(
    [16, silence],
    [16, kick.gain(0.8)],
    [8, kick.gain(0.88)],
    [16, silence],
    [16, kick],
    [16, kick.gain(0.96)],
    [8, kick.gain(0.44)]
  ),

  arrange(
    [16, silence],
    [16, silence],
    [8, clap.gain(0.18)],
    [16, silence],
    [16, clapBloom],
    [16, clap.gain(0.56)],
    [8, silence]
  ),

  arrange(
    [16, hatsPulse.gain(0.03)],
    [16, hatsPulse],
    [8, hatsLift],
    [16, silence],
    [16, hatsBloom],
    [16, hatsLift.gain(0.12)],
    [8, hatsPulse.gain(0.04)]
  ),

  arrange(
    [16, silence],
    [16, silence],
    [8, openHat.gain(0.08)],
    [16, silence],
    [16, openHat],
    [16, openHat.gain(0.16)],
    [8, silence]
  ),

  arrange(
    [16, silence],
    [16, percTop.gain(0.12)],
    [8, percTop.gain(0.18)],
    [16, silence],
    [16, percTop.gain(0.26)],
    [16, percTop.gain(0.22)],
    [8, silence]
  ),

  arrange(
    [16, silence],
    [16, bassPulse],
    [8, bassPulse.gain(0.3)],
    [16, bassGhost],
    [16, bassBloom],
    [16, bassPulse.gain(0.34)],
    [8, silence]
  ),

  arrange(
    [16, padIntro],
    [16, padPulse],
    [8, padPulse.gain(0.16)],
    [16, padBreak.gain(0.82)],
    [16, padPulse.gain(0.18)],
    [16, padPulse.gain(0.14)],
    [8, padIntro]
  ),

  arrange(
    [16, silence],
    [16, pulsePluck],
    [8, pulsePluck.gain(0.06)],
    [16, silence],
    [16, silence],
    [16, pulsePluck.gain(0.04)],
    [8, silence]
  ),

  arrange(
    [16, silence],
    [16, silence],
    [8, silence],
    [16, hookBreak],
    [16, hookBloom],
    [16, hookBreak.gain(0.1)],
    [8, silence]
  ),

  arrange(
    [16, silence],
    [16, silence],
    [8, silence],
    [16, silence],
    [16, arpBloom],
    [16, silence],
    [8, silence]
  ),

  arrange(
    [16, air.gain(0.2)],
    [16, air.gain(0.14)],
    [8, air.gain(0.12)],
    [16, air.gain(0.22)],
    [16, air.gain(0.1)],
    [16, air.gain(0.08)],
    [8, air.gain(0.14)]
  ),

  arrange(
    [16, shimmer.gain(0.08)],
    [16, silence],
    [8, shimmer.gain(0.12)],
    [16, silence],
    [16, shimmer.gain(0.1)],
    [16, silence],
    [8, shimmer.gain(0.08)]
  ),

  arrange(
    [16, silence],
    [16, silence],
    [8, riser.gain(0.1)],
    [16, riser],
    [16, silence],
    [16, silence],
    [8, silence]
  ),

  arrange(
    [16, silence],
    [16, silence],
    [8, silence],
    [16, vocal.gain(0.11)],
    [16, silence],
    [16, vocal.gain(0.08)],
    [8, silence]
  ),

  arrange(
    [16, silence],
    [16, silence],
    [8, silence],
    [16, silence],
    [16, impact],
    [16, silence],
    [8, silence]
  )
)
