// @title Glass Harbor
// @genre melodic / progressive house
// @bpm 124
// @details Pasteable song file for Strudel web. Run `glass-harbor song serve` before pasting.
// @sections intro:8, groove:16, lift:8, breakdown:16, drop:16, breath:8, second-drop:16, outro:8

samples('http://localhost:5432')
setcpm(124 / 4)

const kick = s("kick_main*4")
  .n("0 1 0 1")
  .gain(1)

const clap = s("~ clap_main ~ clap_main")
  .n("0 1")
  .gain(0.5)
  .room(0.14)

const clapLift = clap
  .delay("0.16:0.125:0.12")
  .gain(0.56)

const hatsVerse = s("hat_closed*8")
  .n("0 1 0 2 0 1 0 3")
  .gain("[0.12 0.18 0.12 0.2]*2")
  .pan(sine.range(0.4, 0.6))

const hatsDrop = s("hat_closed*16")
  .n("0 0 1 0 0 2 0 3 0 0 1 0 0 2 0 3")
  .gain("[0.13 0.18 0.16 0.22]*4")
  .pan(sine.range(0.34, 0.66))

const openHat = s("~ hat_open ~ hat_open")
  .n("0 1")
  .gain(0.18)
  .delay("0.16:0.125:0.12")

const percTop = s("~ perc_top ~ perc_top")
  .n("0 1")
  .gain(0.24)
  .delay("0.08:0.125:0.1")

const bassVerse = note("<[d1 ~ ~ a1] [f1 ~ ~ c2] [c2 ~ ~ g1] [a1 ~ ~ e2]>")
  .slow(4)
  .sound("sawtooth,triangle")
  .lpf(580)
  .attack(0.01)
  .decay(0.12)
  .sustain(0.42)
  .release(0.14)
  .gain(0.4)

const bassBreak = note("<[d1 ~ ~ ~] [f1 ~ ~ ~] [c2 ~ ~ ~] [a1 ~ ~ ~]>")
  .slow(4)
  .sound("triangle")
  .lpf(500)
  .attack(0.02)
  .decay(0.16)
  .sustain(0.4)
  .release(0.24)
  .gain(0.24)

const bassDrop = note("<[d1 ~ a1 d2] [f1 ~ c2 f1] [c2 ~ g1 c2] [a1 ~ e2 a1]>")
  .slow(4)
  .sound("sawtooth,triangle")
  .lpf(760)
  .attack(0.01)
  .decay(0.14)
  .sustain(0.46)
  .release(0.12)
  .gain(0.52)

const padBase = note("<[d4,f4,a4,c5,e5] [f3,a3,c4,e4,g4] [c4,e4,g4,b4,d5] [a3,c4,e4,g4,b4]>")
  .slow(4)
  .sound("sawtooth")
  .attack(0.42)
  .decay(0.24)
  .sustain(0.9)
  .release(1.3)
  .room(0.95)
  .delay("0.18:0.25:0.32")

const padIntro = padBase
  .lpf(900)
  .gain(0.1)

const padVerse = padBase
  .lpf(sine.range(950, 2200).slow(16))
  .gain(0.16)

const padBreak = padBase
  .lpf(sine.range(1200, 3000).slow(12))
  .gain(0.22)

const pluck = note("<[~ ~ ~ e5 ~ ~ d5 ~] [~ ~ ~ f5 ~ ~ e5 ~] [~ ~ ~ d5 ~ ~ b4 ~] [~ ~ ~ c5 ~ ~ b4 ~]>")
  .slow(4)
  .sound("triangle")
  .lpf(1750)
  .attack(0.01)
  .decay(0.12)
  .sustain(0.08)
  .release(0.08)
  .delay("0.2:0.125:0.18")
  .room(0.2)
  .gain(0.06)

const leadBreak = note("<[a4 ~ c5 ~ e5 ~ d5 ~] [c5 ~ a4 ~ g4 ~ e4 ~] [g4 ~ b4 ~ d5 ~ e5 ~] [e5 ~ c5 ~ a4 ~ g4 ~]>")
  .slow(4)
  .sound("sawtooth")
  .vowel("<a e i o>")
  .lpf(1640)
  .attack(0.11)
  .decay(0.16)
  .sustain(0.46)
  .release(0.7)
  .delay("0.54:0.125:0.62")
  .room(0.88)
  .gain(0.13)

const leadDrop = note("<[a4 c5 ~ e5 ~ d5 c5 ~] [c5 a4 ~ g4 ~ e4 g4 ~] [g4 b4 ~ d5 ~ e5 d5 ~] [e5 c5 ~ a4 ~ g4 a4 ~]>")
  .slow(4)
  .sound("sawtooth")
  .vowel("<a e o i>")
  .lpf(2360)
  .attack(0.05)
  .decay(0.14)
  .sustain(0.3)
  .release(0.24)
  .delay("0.18:0.125:0.14")
  .room(0.18)
  .gain(0.14)

const arp = note("<[d4 a4 c5 a4 e5 a4 c5 a4] [f4 a4 c5 a4 e5 a4 c5 a4] [c4 g4 b4 g4 d5 g4 b4 g4] [a3 e4 g4 e4 c5 e4 g4 e4]>")
  .slow(4)
  .sound("triangle")
  .lpf(saw.range(950, 2100).slow(8))
  .attack(0.01)
  .decay(0.14)
  .sustain(0.16)
  .release(0.1)
  .delay("0.22:0.125:0.2")
  .room(0.24)
  .gain(0.08)

const air = s("air_texture")
  .slow(8)
  .gain(0.2)
  .room(1)
  .lpf(sine.range(700, 2600).slow(8))

const riser = s("riser_up")
  .slow(8)
  .gain(0.16)
  .room(0.92)

const shimmer = s("shimmer_fx")
  .slow(4)
  .gain(0.12)

const vocal = s("vocal_chop")
  .gain(0.14)
  .delay("0.12:0.25:0.14")

const impact = s("impact_wide")
  .gain(0.34)

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
    [16, clapLift],
    [8, silence],
    [16, clapLift.gain(0.62)],
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
    [8, bassVerse.gain(0.5)],
    [16, bassBreak],
    [16, bassDrop],
    [8, silence],
    [16, bassDrop.gain(0.58)],
    [8, silence]
  ),

  arrange(
    [8, padIntro],
    [16, padVerse],
    [8, padVerse.gain(0.2)],
    [16, padBreak],
    [16, padVerse],
    [8, padIntro],
    [16, padVerse.gain(0.22)],
    [8, padIntro]
  ),

  arrange(
    [8, silence],
    [16, pluck],
    [8, pluck.gain(0.05)],
    [16, silence],
    [16, pluck.gain(0.06)],
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
    [16, leadDrop.gain(0.148)],
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
    [16, arp.gain(0.09)],
    [8, silence]
  )
)
