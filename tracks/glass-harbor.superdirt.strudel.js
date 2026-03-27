// @title Glass Harbor SuperDirt Performance
// @details Hybrid arrangement: local sample pack for drums and FX, OSC to SuperDirt for tonal parts.

samples('__SAMPLE_PACK_URL__')
setcpm(124 / 4)

const kick = s("kick_main*4")
  .n("0 1 0 1")
  .gain(1)

const clap = s("~ clap_main ~ clap_main")
  .n("0 1")
  .gain(0.48)
  .room(0.1)

const hatsVerse = s("hat_closed*8")
  .n("0 1 0 2 0 1 0 3")
  .gain("[0.12 0.16 0.12 0.2]*2")

const hatsDrop = s("hat_closed*16")
  .n("0 0 1 0 0 2 0 3 0 0 1 0 0 2 0 3")
  .gain("[0.13 0.18 0.16 0.22]*4")

const openHat = s("~ hat_open ~ hat_open")
  .n("0 1")
  .gain(0.18)

const percTop = s("~ perc_top ~ perc_top")
  .n("0 1")
  .gain(0.24)

const air = s("air_texture")
  .slow(8)
  .gain(0.2)

const riser = s("riser_up")
  .slow(8)
  .gain(0.16)

const shimmer = s("shimmer_fx")
  .slow(4)
  .gain(0.12)

const vocal = s("vocal_chop")
  .gain(0.13)
  .delay("0.12:0.25:0.14")

const impact = s("impact_wide")
  .gain(0.34)

const bassVerse = note("<[d1 ~ ~ a1] [f1 ~ ~ c2] [c2 ~ ~ g1] [a1 ~ ~ e2]>")
  .slow(4)
  .sound("supersquare")
  .cutoff(820)
  .resonance(0.28)
  .gain(0.78)
  .osc()

const bassBreak = note("<[d1 ~ ~ ~] [f1 ~ ~ ~] [c2 ~ ~ ~] [a1 ~ ~ ~]>")
  .slow(4)
  .sound("supersquare")
  .cutoff(620)
  .resonance(0.18)
  .gain(0.58)
  .osc()

const bassDrop = note("<[d1 ~ a1 d2] [f1 ~ c2 f1] [c2 ~ g1 c2] [a1 ~ e2 a1]>")
  .slow(4)
  .sound("supersquare")
  .cutoff(1040)
  .resonance(0.34)
  .gain(0.92)
  .osc()

const padIntro = note("<[d4,f4,a4,c5,e5] [f3,a3,c4,e4,g4] [c4,e4,g4,b4,d5] [a3,c4,e4,g4,b4]>")
  .slow(4)
  .sound("supersaw")
  .cutoff(1200)
  .resonance(0.18)
  .gain(0.28)
  .osc()

const padVerse = note("<[d4,f4,a4,c5,e5] [f3,a3,c4,e4,g4] [c4,e4,g4,b4,d5] [a3,c4,e4,g4,b4]>")
  .slow(4)
  .sound("supersaw")
  .cutoff(sine.range(1200, 2800).slow(16))
  .resonance(0.24)
  .gain(0.34)
  .osc()

const padBreak = note("<[d4,f4,a4,c5,e5] [f3,a3,c4,e4,g4] [c4,e4,g4,b4,d5] [a3,c4,e4,g4,b4]>")
  .slow(4)
  .sound("supersaw")
  .cutoff(sine.range(1600, 3400).slow(12))
  .resonance(0.3)
  .gain(0.38)
  .osc()

const pluck = note("<[~ ~ ~ e5 ~ ~ d5 ~] [~ ~ ~ f5 ~ ~ e5 ~] [~ ~ ~ d5 ~ ~ b4 ~] [~ ~ ~ c5 ~ ~ b4 ~]>")
  .slow(4)
  .sound("superpwm")
  .cutoff(2200)
  .resonance(0.16)
  .gain(0.34)
  .osc()

const leadBreak = note("<[a4 ~ c5 ~ e5 ~ d5 ~] [c5 ~ a4 ~ g4 ~ e4 ~] [g4 ~ b4 ~ d5 ~ e5 ~] [e5 ~ c5 ~ a4 ~ g4 ~]>")
  .slow(4)
  .sound("supersaw")
  .cutoff(2400)
  .resonance(0.3)
  .gain(0.42)
  .osc()

const leadDrop = note("<[a4 c5 ~ e5 ~ d5 c5 ~] [c5 a4 ~ g4 ~ e4 g4 ~] [g4 b4 ~ d5 ~ e5 d5 ~] [e5 c5 ~ a4 ~ g4 a4 ~]>")
  .slow(4)
  .sound("supersaw")
  .cutoff(3200)
  .resonance(0.34)
  .gain(0.52)
  .osc()

const arp = note("<[d4 a4 c5 a4 e5 a4 c5 a4] [f4 a4 c5 a4 e5 a4 c5 a4] [c4 g4 b4 g4 d5 g4 b4 g4] [a3 e4 g4 e4 c5 e4 g4 e4]>")
  .slow(4)
  .sound("superpwm")
  .cutoff(saw.range(1800, 3200).slow(8))
  .resonance(0.18)
  .gain(0.32)
  .osc()

stack(
  arrange(
    [8, silence],
    [16, kick],
    [8, kick],
    [16, silence],
    [16, kick],
    [8, silence],
    [16, kick],
    [8, kick.gain(0.6)]
  ),

  arrange(
    [8, silence],
    [16, clap],
    [8, clap],
    [16, silence],
    [16, clap.gain(0.54)],
    [8, silence],
    [16, clap.gain(0.6)],
    [8, silence]
  ),

  arrange(
    [8, hatsVerse.gain(0.08)],
    [16, hatsVerse],
    [8, hatsVerse.gain(0.12)],
    [16, silence],
    [16, hatsDrop],
    [8, hatsVerse.gain(0.1)],
    [16, hatsDrop.gain(0.16)],
    [8, hatsVerse.gain(0.08)]
  ),

  arrange(
    [8, silence],
    [16, silence],
    [8, openHat.gain(0.12)],
    [16, silence],
    [16, openHat],
    [8, silence],
    [16, openHat.gain(0.18)],
    [8, silence]
  ),

  arrange(
    [8, silence],
    [16, percTop.gain(0.16)],
    [8, percTop.gain(0.18)],
    [16, silence],
    [16, percTop.gain(0.22)],
    [8, silence],
    [16, percTop.gain(0.26)],
    [8, silence]
  ),

  arrange(
    [8, silence],
    [16, bassVerse],
    [8, bassVerse.gain(0.72)],
    [16, bassBreak],
    [16, bassDrop],
    [8, silence],
    [16, bassDrop.gain(0.96)],
    [8, silence]
  ),

  arrange(
    [8, padIntro],
    [16, padVerse],
    [8, padVerse.gain(0.28)],
    [16, padBreak],
    [16, padVerse],
    [8, padIntro],
    [16, padVerse.gain(0.36)],
    [8, padIntro]
  ),

  arrange(
    [8, silence],
    [16, pluck],
    [8, pluck.gain(0.3)],
    [16, silence],
    [16, pluck.gain(0.36)],
    [8, silence],
    [16, silence],
    [8, silence]
  ),

  arrange(
    [8, silence],
    [16, silence],
    [8, silence],
    [16, leadBreak],
    [16, leadDrop],
    [8, silence],
    [16, leadDrop.gain(0.58)],
    [8, silence]
  ),

  arrange(
    [8, air],
    [16, silence],
    [8, riser.gain(0.14)],
    [15, air.gain(0.22)],
    [1, impact],
    [15, riser.gain(0.08)],
    [1, impact.gain(0.4)],
    [8, air.gain(0.18)],
    [15, riser.gain(0.14)],
    [1, impact.gain(0.42)],
    [8, air]
  ),

  arrange(
    [8, silence],
    [16, silence],
    [8, vocal.slow(2)],
    [16, silence],
    [16, vocal.fast(2).gain(0.12)],
    [8, silence],
    [16, shimmer],
    [8, air]
  ),

  arrange(
    [8, silence],
    [16, silence],
    [8, silence],
    [16, silence],
    [16, silence],
    [8, silence],
    [16, arp.gain(0.36)],
    [8, silence]
  )
)
