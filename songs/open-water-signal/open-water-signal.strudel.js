// @title Open Water Signal
// @genre emotional progressive house / melodic electronica
// @bpm 120
// @details Pasteable song file for Strudel web. Run `glass-harbor song serve` before pasting.
// @sections intro:16, pulse:16, lift:8, breakdown:16, bloom:16, afterglow:16, outro:8

samples('http://localhost:5432')
setcpm(120 / 4)

const kick = s("kick_main*4")
  .n("0 1 0 1")
  .gain(0.96)

const clap = s("~ clap_main ~ clap_main")
  .n("0 1")
  .gain(0.42)
  .room(0.16)

const clapLift = clap
  .delay("0.22:0.125:0.14")
  .gain(0.48)

const hatsPulse = s("hat_closed*8")
  .n("0 1 0 2 0 1 0 3")
  .gain("[0.08 0.12 0.08 0.14]*2")
  .pan(sine.range(0.38, 0.62))

const hatsBloom = s("hat_closed*16")
  .n("0 0 1 0 0 2 0 3 0 0 1 0 0 2 0 4")
  .gain("[0.09 0.12 0.11 0.15]*4")
  .pan(sine.range(0.32, 0.68))

const openHat = s("~ hat_open ~ hat_open")
  .n("0 1")
  .gain(0.16)
  .delay("0.14:0.125:0.1")

const percTop = s("~ perc_top ~ perc_top")
  .n("0 1")
  .gain(0.18)
  .delay("0.08:0.125:0.12")

const bassPulse = note("<[a1 ~ e2 ~] [f1 ~ c2 ~] [c2 ~ g1 ~] [g1 ~ d2 ~]>")
  .slow(4)
  .sound("triangle")
  .lpf(540)
  .attack(0.02)
  .decay(0.16)
  .sustain(0.42)
  .release(0.24)
  .gain(0.28)

const bassBreak = note("<[a1 ~ ~ ~] [f1 ~ ~ ~] [c2 ~ ~ ~] [g1 ~ ~ ~]>")
  .slow(4)
  .sound("triangle")
  .lpf(430)
  .attack(0.03)
  .decay(0.14)
  .sustain(0.38)
  .release(0.34)
  .gain(0.22)

const bassBloom = note("<[a1 ~ e2 a1] [f1 ~ c2 a1] [c2 ~ g1 c2] [g1 ~ d2 b1]>")
  .slow(4)
  .sound("sawtooth,triangle")
  .lpf(780)
  .attack(0.01)
  .decay(0.12)
  .sustain(0.46)
  .release(0.14)
  .gain(0.48)

const padBase = note("<[a3,c4,e4,g4,b4] [f3,a3,c4,e4,g4] [c4,e4,g4,b4,d5] [g3,b3,d4,f4,a4]>")
  .slow(4)
  .sound("sawtooth")
  .attack(0.54)
  .decay(0.22)
  .sustain(0.94)
  .release(1.5)
  .room(0.96)
  .delay("0.24:0.25:0.34")

const padIntro = padBase
  .lpf(760)
  .gain(0.11)

const padPulse = padBase
  .lpf(sine.range(900, 1800).slow(16))
  .gain(0.16)

const padBreak = padBase
  .lpf(sine.range(1200, 2900).slow(12))
  .gain(0.22)

const pulsePluck = note("<[~ ~ e5 ~ ~ ~ g5 ~] [~ ~ c5 ~ ~ ~ e5 ~] [~ ~ g4 ~ ~ ~ b4 ~] [~ ~ d5 ~ ~ ~ c5 ~]>")
  .slow(4)
  .sound("triangle")
  .lpf(1550)
  .attack(0.01)
  .decay(0.14)
  .sustain(0.08)
  .release(0.1)
  .delay("0.22:0.125:0.18")
  .room(0.28)
  .gain(0.05)

const leadBreak = note("<[e5 ~ g5 ~ a5 ~ g5 ~] [c5 ~ e5 ~ g5 ~ e5 ~] [g4 ~ b4 ~ d5 ~ b4 ~] [d5 ~ c5 ~ b4 ~ a4 ~]>")
  .slow(4)
  .sound("sawtooth")
  .vowel("<a e i o>")
  .lpf(1700)
  .attack(0.16)
  .decay(0.2)
  .sustain(0.48)
  .release(0.9)
  .delay("0.56:0.125:0.62")
  .room(0.9)
  .gain(0.12)

const leadBloom = note("<[e5 g5 ~ a5 ~ g5 e5 ~] [c5 e5 ~ g5 ~ e5 c5 ~] [g4 b4 ~ d5 ~ b4 g4 ~] [d5 c5 ~ b4 ~ a4 g4 ~]>")
  .slow(4)
  .sound("sawtooth")
  .vowel("<a e o i>")
  .lpf(2300)
  .attack(0.06)
  .decay(0.16)
  .sustain(0.34)
  .release(0.34)
  .delay("0.24:0.125:0.18")
  .room(0.26)
  .gain(0.15)

const arpBloom = note("<[a4 e5 g5 e5 a5 e5 g5 e5] [f4 c5 e5 c5 g5 c5 e5 c5] [c5 g5 b5 g5 d5 g5 b5 g5] [g4 d5 f5 d5 a5 d5 f5 d5]>")
  .slow(4)
  .sound("triangle")
  .lpf(saw.range(1100, 2400).slow(8))
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
  .lpf(sine.range(650, 2500).slow(10))

const riser = s("riser_up")
  .slow(8)
  .gain(0.14)
  .room(0.94)

const shimmer = s("shimmer_fx")
  .slow(8)
  .gain(0.12)

const vocal = s("vocal_chop")
  .delay("0.18:0.25:0.14")
  .gain(0.11)

const impact = s("impact_wide ~ ~ ~")
  .slow(4)
  .gain(0.26)

stack(
  arrange(
    [16, silence],
    [16, kick.gain(0.86)],
    [8, kick.gain(0.92)],
    [16, silence],
    [16, kick],
    [16, kick.gain(0.92)],
    [8, kick.gain(0.52)]
  ),

  arrange(
    [16, silence],
    [16, silence],
    [8, clapLift.gain(0.3)],
    [16, silence],
    [16, clap],
    [16, clapLift],
    [8, silence]
  ),

  arrange(
    [16, hatsPulse.gain(0.05)],
    [16, hatsPulse],
    [8, hatsPulse.gain(0.14)],
    [16, silence],
    [16, hatsBloom],
    [16, hatsBloom.gain(0.12)],
    [8, hatsPulse.gain(0.06)]
  ),

  arrange(
    [16, silence],
    [16, silence],
    [8, openHat.gain(0.08)],
    [16, silence],
    [16, openHat],
    [16, openHat.gain(0.18)],
    [8, silence]
  ),

  arrange(
    [16, silence],
    [16, percTop.gain(0.12)],
    [8, percTop.gain(0.16)],
    [16, silence],
    [16, percTop.gain(0.2)],
    [16, percTop.gain(0.22)],
    [8, silence]
  ),

  arrange(
    [16, silence],
    [16, bassPulse],
    [8, bassPulse.gain(0.34)],
    [16, bassBreak],
    [16, bassBloom],
    [16, bassBloom.gain(0.42)],
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
    [16, leadBreak],
    [16, leadBloom],
    [16, leadBloom.gain(0.12)],
    [8, silence]
  ),

  arrange(
    [16, silence],
    [16, silence],
    [8, silence],
    [16, silence],
    [16, arpBloom],
    [16, arpBloom.gain(0.06)],
    [8, silence]
  ),

  arrange(
    [16, air],
    [16, air.gain(0.14)],
    [8, air.gain(0.18)],
    [16, air.gain(0.22)],
    [16, air.gain(0.18)],
    [16, air.gain(0.14)],
    [8, air.gain(0.12)]
  ),

  arrange(
    [16, silence],
    [16, silence],
    [8, shimmer.gain(0.12)],
    [16, shimmer.gain(0.14)],
    [16, shimmer.gain(0.08)],
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
    [16, riser],
    [16, silence],
    [16, silence],
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
