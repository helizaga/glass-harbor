// @title Horizon Answer
// @genre emotional progressive house / melodic electronica
// @bpm 122
// @details Pasteable song file for Strudel web. Run `glass-harbor song serve` before pasting.
// @sections intro:16, pulse:16, lift:8, breakdown:16, bloom:16, release:16, outro:8

samples('http://localhost:5432')
setcpm(122 / 4)

const kick = s("kick_main*4")
  .n("0 1 0 1")
  .gain(1.02)

const clap = s("~ clap_main ~ clap_main")
  .n("0 1")
  .gain(0.48)
  .room(0.14)

const clapWide = clap
  .delay("0.18:0.125:0.12")
  .gain(0.58)

const hatsPulse = s("hat_closed*8")
  .n("0 1 0 2 0 1 0 3")
  .gain("[0.08 0.1 0.08 0.12]*2")
  .pan(sine.range(0.4, 0.6))

const hatsBloom = s("hat_closed*16")
  .n("0 0 1 0 0 2 0 3 0 0 1 0 0 2 0 4")
  .gain("[0.1 0.13 0.11 0.16]*4")
  .pan(sine.range(0.34, 0.66))

const openHat = s("~ hat_open ~ hat_open")
  .n("0 1")
  .gain(0.18)
  .delay("0.12:0.125:0.09")

const percTop = s("~ perc_top ~ perc_top")
  .n("0 1")
  .gain(0.22)
  .delay("0.08:0.125:0.12")

const bassPulse = note("<[f#1 ~ c#2 ~] [d1 ~ a1 ~] [a1 ~ e2 ~] [e1 ~ b1 ~]>")
  .slow(4)
  .sound("triangle")
  .lpf(560)
  .attack(0.02)
  .decay(0.14)
  .sustain(0.42)
  .release(0.22)
  .gain(0.32)

const bassBreak = note("<[f#1 ~ ~ ~] [d1 ~ ~ ~] [a1 ~ ~ ~] [e1 ~ ~ ~]>")
  .slow(4)
  .sound("triangle")
  .lpf(420)
  .attack(0.03)
  .decay(0.14)
  .sustain(0.36)
  .release(0.34)
  .gain(0.18)

const bassBloom = note("<[f#1 ~ c#2 f#1] [d1 ~ a1 d2] [a1 ~ e2 a1] [e1 ~ b1 e2]>")
  .slow(4)
  .sound("sawtooth,triangle")
  .lpf(840)
  .attack(0.01)
  .decay(0.12)
  .sustain(0.5)
  .release(0.14)
  .gain(0.56)

const padBase = note("<[f#3,a3,c#4,e4,g#4] [d3,f#3,a3,c#4,e4] [a3,c#4,e4,g#4,b4] [e3,g#3,b3,d4,f#4]>")
  .slow(4)
  .sound("sawtooth")
  .attack(0.5)
  .decay(0.22)
  .sustain(0.94)
  .release(1.6)
  .room(0.96)
  .delay("0.22:0.25:0.34")

const padIntro = padBase
  .lpf(780)
  .gain(0.1)

const padPulse = padBase
  .lpf(sine.range(980, 1900).slow(16))
  .gain(0.15)

const padBreak = padBase
  .lpf(sine.range(1300, 3200).slow(12))
  .gain(0.22)

const pluckPulse = note("<[~ ~ c#5 ~ ~ ~ e5 ~] [~ ~ a4 ~ ~ ~ c#5 ~] [~ ~ e5 ~ ~ ~ g#5 ~] [~ ~ b4 ~ ~ ~ a4 ~]>")
  .slow(4)
  .sound("triangle")
  .lpf(1600)
  .attack(0.01)
  .decay(0.14)
  .sustain(0.08)
  .release(0.1)
  .delay("0.24:0.125:0.2")
  .room(0.24)
  .gain(0.05)

const hookBreak = note("<[c#5 ~ e5 ~ f#5 ~ e5 ~] [a4 ~ c#5 ~ e5 ~ c#5 ~] [e5 ~ g#5 ~ a5 ~ g#5 ~] [b4 ~ a4 ~ g#4 ~ f#4 ~]>")
  .slow(4)
  .sound("sawtooth")
  .vowel("<a e i o>")
  .lpf(1760)
  .attack(0.14)
  .decay(0.18)
  .sustain(0.48)
  .release(0.88)
  .delay("0.54:0.125:0.62")
  .room(0.9)
  .gain(0.12)

const hookBloom = note("<[c#5 e5 ~ f#5 ~ e5 c#5 ~] [a4 c#5 ~ e5 ~ c#5 a4 ~] [e5 g#5 ~ a5 ~ g#5 e5 ~] [b4 a4 ~ g#4 ~ f#4 e4 ~]>")
  .slow(4)
  .sound("sawtooth")
  .vowel("<a e o i>")
  .lpf(2380)
  .attack(0.05)
  .decay(0.14)
  .sustain(0.34)
  .release(0.28)
  .delay("0.2:0.125:0.16")
  .room(0.24)
  .gain(0.16)

const arpBloom = note("<[f#4 c#5 e5 c#5 a5 c#5 e5 c#5] [d4 a4 c#5 a4 f#5 a4 c#5 a4] [a4 e5 g#5 e5 c#5 e5 g#5 e5] [e4 b4 d5 b4 g#5 b4 d5 b4]>")
  .slow(4)
  .sound("triangle")
  .lpf(saw.range(1200, 2500).slow(8))
  .attack(0.01)
  .decay(0.12)
  .sustain(0.18)
  .release(0.1)
  .delay("0.18:0.125:0.16")
  .room(0.22)
  .gain(0.08)

const air = s("air_texture")
  .slow(8)
  .gain(0.18)
  .room(1)
  .lpf(sine.range(700, 2600).slow(10))

const shimmer = s("shimmer_fx")
  .slow(8)
  .gain(0.12)

const riser = s("riser_up")
  .slow(8)
  .gain(0.18)
  .room(0.96)

const vocal = s("vocal_chop")
  .delay("0.18:0.25:0.14")
  .gain(0.1)

const impact = s("impact_wide ~ ~ ~")
  .slow(4)
  .gain(0.34)

stack(
  arrange(
    [16, silence],
    [16, kick.gain(0.82)],
    [8, kick.gain(0.88)],
    [16, silence],
    [16, kick],
    [16, kick.gain(0.94)],
    [8, kick.gain(0.46)]
  ),

  arrange(
    [16, silence],
    [16, silence],
    [8, clapWide.gain(0.28)],
    [16, silence],
    [16, clapWide],
    [16, clapWide.gain(0.64)],
    [8, silence]
  ),

  arrange(
    [16, hatsPulse.gain(0.04)],
    [16, hatsPulse],
    [8, hatsPulse.gain(0.16)],
    [16, silence],
    [16, hatsBloom],
    [16, hatsBloom.gain(0.14)],
    [8, hatsPulse.gain(0.05)]
  ),

  arrange(
    [16, silence],
    [16, silence],
    [8, openHat.gain(0.08)],
    [16, silence],
    [16, openHat],
    [16, openHat.gain(0.2)],
    [8, silence]
  ),

  arrange(
    [16, silence],
    [16, percTop.gain(0.12)],
    [8, percTop.gain(0.2)],
    [16, silence],
    [16, percTop.gain(0.24)],
    [16, percTop.gain(0.26)],
    [8, silence]
  ),

  arrange(
    [16, silence],
    [16, bassPulse],
    [8, bassPulse.gain(0.36)],
    [16, bassBreak],
    [16, bassBloom],
    [16, bassBloom.gain(0.62)],
    [8, silence]
  ),

  arrange(
    [16, padIntro],
    [16, padPulse],
    [8, padPulse.gain(0.18)],
    [16, padBreak],
    [16, padPulse.gain(0.2)],
    [16, padPulse.gain(0.16)],
    [8, padIntro]
  ),

  arrange(
    [16, silence],
    [16, pluckPulse],
    [8, pluckPulse.gain(0.06)],
    [16, silence],
    [16, silence],
    [16, pluckPulse.gain(0.04)],
    [8, silence]
  ),

  arrange(
    [16, silence],
    [16, silence],
    [8, silence],
    [16, hookBreak],
    [16, hookBloom],
    [16, hookBloom.gain(0.14)],
    [8, silence]
  ),

  arrange(
    [16, silence],
    [16, silence],
    [8, silence],
    [16, silence],
    [16, arpBloom],
    [16, arpBloom.gain(0.1)],
    [8, silence]
  ),

  arrange(
    [16, air],
    [16, air.gain(0.14)],
    [8, air.gain(0.18)],
    [16, air.gain(0.26)],
    [16, air.gain(0.16)],
    [16, air.gain(0.12)],
    [8, air.gain(0.1)]
  ),

  arrange(
    [16, shimmer.gain(0.08)],
    [16, silence],
    [8, shimmer.gain(0.12)],
    [16, shimmer.gain(0.14)],
    [16, silence],
    [16, silence],
    [8, silence]
  ),

  arrange(
    [16, silence],
    [16, silence],
    [8, vocal.gain(0.08)],
    [16, vocal],
    [16, vocal.gain(0.12)],
    [16, silence],
    [8, silence]
  ),

  arrange(
    [16, silence],
    [16, silence],
    [8, riser.gain(0.12)],
    [16, riser.gain(0.18)],
    [16, silence],
    [16, silence],
    [8, silence]
  ),

  arrange(
    [16, silence],
    [16, silence],
    [8, silence],
    [16, silence],
    [16, impact.gain(0.34)],
    [16, silence],
    [8, silence]
  )
)
