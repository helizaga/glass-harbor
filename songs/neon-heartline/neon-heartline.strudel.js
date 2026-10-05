// @title Neon Heartline
// @genre edm crossover / melodic dance-pop
// @bpm 124
// @details Pasteable song file for Strudel web. Run `glass-harbor song serve` before pasting. Original hook-first dance track with a clean pocket, sampled tonal layers, and a wide return.
// @sections intro:8, groove:16, lift:8, breakdown:8, return:16, outro:8
// @section_roles intro:anchor, groove:groove, lift:lift, breakdown:breath, return:return, outro:outro

samples('http://localhost:5432')
setcpm(124 / 4)

const kickGroove = s("kick_main*4")
  .n("0 1 0 1")
  .gain("[0.92 0.86 0.9 0.84]")

const kickReturn = s("kick_main*8")
  .n("0 1 0 1 0 1 0 1")
  .gain("[0.94 0.84 0.92 0.82]*2")

const kickIntro = s("kick_main*4")
  .n("0 ~ ~ 1")
  .gain("[0.18 0 0 0.14]")

const kickBreak = s("kick_main*4")
  .n("0 ~ ~ ~")
  .gain("[0.26 0 0 0]")

const clapMain = s("~ clap_main ~ clap_main")
  .n("0 1")
  .gain(0.34)
  .room(0.12)

const clapLift = clapMain.gain(0.24)

const hatsGroove = s("hat_closed*8")
  .n("0 1 0 2 0 1 0 3")
  .gain("[0.038 0.064 0.038 0.074]*2")
  .pan(sine.range(0.42, 0.58))

const hatsLift = s("hat_closed*8")
  .n("0 1 0 2 0 3 0 4")
  .gain("[0.042 0.072 0.042 0.082]*2")
  .pan(sine.range(0.38, 0.62))

const openHat = s("~ hat_open ~ ~ ~ hat_open ~ ~")
  .n("0 1")
  .gain(0.058)

const percMotion = s("perc_top*8")
  .n("0 ~ 1 ~ 0 ~ 1 0")
  .gain("[0.03 0 0.055 0 0.04 0 0.065 0.03]")
  .delay("0.02:0.125:0.035")

const bassGroove = s("bass_tonal*8")
  .n("0 ~ 1 ~ 0 ~ 2 ~")
  .gain("[0.12 0 0.105 0 0.128 0 0.11 0]")
  .lpf(290)
  .room(0.04)

const bassLift = s("bass_tonal*8")
  .n("0 ~ 1 ~ 0 ~ 2 ~")
  .gain("[0.116 0 0.09 0 0.126 0 0.098 0]")
  .lpf(340)
  .room(0.04)

const bassBreak = s("bass_tonal*8")
  .n("0 ~ ~ ~ 1 ~ ~ ~")
  .gain("[0.094 0 0 0 0.084 0 0 0]")
  .lpf(270)

const stabBed = s("stab_tonal*8")
  .n("0 ~ 1 ~ 0 ~ 1 ~")
  .gain("[0.065 0 0.054 0 0.072 0 0.06 0]")
  .lpf(1450)
  .delay("0.05:0.125:0.04")
  .room(0.12)

const stabLift = s("stab_tonal*8")
  .n("0 0 1 ~ 0 2 0 1")
  .gain("[0.075 0.03 0.06 0 0.082 0.038 0.064 0.046]")
  .lpf(sine.range(1300, 2200).slow(8))
  .delay("0.05:0.125:0.05")
  .room(0.18)

const pluckHook = s("pluck_tonal*16")
  .n("0 ~ 1 ~ 0 1 0 2 0 ~ 3 ~ 1 4 2 5")
  .gain("[0.034 0 0.055 0 0.04 0.064 0.044 0.07 0.036 0 0.06 0 0.05 0.076 0.054 0.082]")
  .lpf(sine.range(900, 1800).slow(8))
  .delay("0.04:0.125:0.05")

const pluckReturn = s("pluck_tonal*16")
  .n("0 1 0 2 0 3 1 4 0 2 1 5 0 3 2 4")
  .gain("[0.048 0.074 0.052 0.084 0.054 0.09 0.058 0.096]*2")
  .lpf(sine.range(1100, 2100).slow(8))
  .delay("0.04:0.125:0.05")

const pluckIntro = s("pluck_tonal*4")
  .n("0 ~ 1 ~")
  .gain("[0.038 0 0.058 0]")
  .lpf(1350)
  .delay("0.03:0.125:0.04")

const pluckBreak = s("pluck_tonal*4")
  .n("0 ~ ~ 1")
  .gain("[0.04 0 0 0.058]")
  .lpf(1200)

const vocalMist = s("vocal_chop*8")
  .n("0 1 2 1 0 3 2 1")
  .gain("[0.026 0.042 0.03 0.046]*2")
  .lpf(2100)
  .pan(sine.range(0.34, 0.66))

const vocalLift = s("vocal_chop*8")
  .n("0 2 1 3 0 4 2 5")
  .gain("[0.042 0.068 0.048 0.078]*2")
  .lpf(2400)
  .pan(sine.range(0.28, 0.72))

const vocalBreak = s("vocal_chop*4")
  .n("0 ~ 2 ~")
  .gain("[0.04 0 0.056 0]")
  .lpf(2400)

const air = s("air_texture")
  .slow(8)
  .gain(0.045)
  .room(0.7)
  .lpf(sine.range(850, 1700).slow(8))

const shimmer = s("shimmer_fx")
  .slow(8)
  .gain(0.025)

const riser = s("riser_up")
  .slow(8)
  .gain(0.045)

const impact = s("impact_wide ~ ~ ~")
  .slow(4)
  .gain(0.075)

const octaveGhost = note("<[e5 ~ b5 ~ g5 ~ d6 ~] [d5 ~ a5 ~ f5 ~ c6 ~] [c5 ~ g5 ~ e5 ~ bb5 ~] [b4 ~ fs5 ~ d5 ~ a5 ~]>")
  .slow(4)
  .sound("sine")
  .lpf(sine.range(1200, 2200).slow(8))
  .attack(0.02)
  .decay(0.12)
  .sustain(0.08)
  .release(0.18)
  .delay("0.08:0.125:0.06")
  .room(0.18)
  .gain(0.026)

stack(
  arrange(
    [8, kickIntro],
    [16, kickGroove],
    [8, kickGroove.gain(0.94)],
    [8, kickBreak],
    [16, kickReturn.gain(1.02)],
    [8, kickIntro.gain(0.4)]
  ),

  arrange(
    [8, silence],
    [16, clapMain],
    [8, clapLift],
    [8, silence],
    [16, clapMain.gain(1.04)],
    [8, silence]
  ),

  arrange(
    [8, hatsGroove.gain(0.28)],
    [16, hatsGroove],
    [8, hatsLift],
    [8, silence],
    [16, hatsLift.gain(0.96)],
    [8, hatsGroove.gain(0.2)]
  ),

  arrange(
    [8, silence],
    [16, silence],
    [8, openHat.gain(0.06)],
    [8, silence],
    [16, openHat.gain(0.1)],
    [8, silence]
  ),

  arrange(
    [8, percMotion.gain(0.22)],
    [16, percMotion],
    [8, percMotion.gain(0.9)],
    [8, percMotion.gain(0.2)],
    [16, percMotion.gain(0.98)],
    [8, percMotion.gain(0.16)]
  ),

  arrange(
    [8, silence],
    [16, bassGroove],
    [8, bassLift.gain(0.92)],
    [8, bassBreak],
    [16, bassLift],
    [8, silence]
  ),

  arrange(
    [8, stabBed.gain(0.45)],
    [16, stabBed],
    [8, stabLift],
    [8, stabBed.gain(0.54)],
    [16, stabLift.gain(0.94)],
    [8, stabBed.gain(0.66)]
  ),

  arrange(
    [8, pluckIntro],
    [16, pluckHook.gain(0.74)],
    [8, pluckHook],
    [8, pluckBreak],
    [16, pluckReturn.gain(1.08)],
    [8, pluckIntro.gain(0.7)]
  ),

  arrange(
    [8, vocalMist.gain(0.28)],
    [16, vocalMist],
    [8, vocalLift],
    [8, vocalBreak],
    [16, vocalLift.gain(1.12)],
    [8, vocalMist.gain(0.54)]
  ),

  arrange(
    [8, silence],
    [16, octaveGhost.gain(0.46)],
    [8, octaveGhost.gain(0.72)],
    [8, octaveGhost.gain(0.2)],
    [16, octaveGhost.gain(0.4)],
    [8, silence]
  ),

  arrange(
    [8, air.gain(0.4)],
    [16, air.gain(0.09)],
    [8, shimmer.gain(0.05)],
    [8, air.gain(0.38)],
    [16, air.gain(0.1)],
    [8, air.gain(0.08)]
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
