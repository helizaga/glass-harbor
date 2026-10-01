// @title Phoneglow Aftertaste
// @genre soft garage / intimate r&b-pop study
// @bpm 106
// @details Pasteable song file for Strudel web. Run `glass-harbor song serve` before pasting. Original study blending featherlight hook energy, warm pocket, and dry low-mid restraint.
// @sections intro:8, pocket:16, hook:8, breakdown:8, return:16, outro:8
// @section_roles intro:anchor, pocket:groove, hook:lift, breakdown:breath, return:return, outro:outro

samples('http://localhost:5432')
setcpm(106 / 4)

const kickPocket = s("kick_main*8")
  .n("0 ~ ~ 1 ~ 0 ~ ~")
  .gain("[0.9 0 0 0.7 0 0.88 0 0]")

const kickReturn = s("kick_main*8")
  .n("0 ~ 1 ~ 0 ~ 1 ~")
  .gain("[0.94 0 0.68 0 0.92 0 0.72 0]")

const clapPocket = s("~ ~ clap_main ~ ~ ~ clap_main ~")
  .n("0 1")
  .gain(0.34)
  .room(0.12)

const hatsPocket = s("hat_closed*16")
  .n("0 1 0 2 0 1 0 3 0 1 0 2 0 1 0 4")
  .gain("[0.04 0.07 0.04 0.09]*4")
  .pan(sine.range(0.42, 0.58))

const hatsReturn = s("hat_closed*16")
  .n("0 1 0 2 0 3 0 4 0 1 0 2 0 3 0 5")
  .gain("[0.05 0.09 0.05 0.1]*4")
  .pan(sine.range(0.36, 0.64))

const openHat = s("~ hat_open ~ ~ ~ hat_open ~ ~")
  .n("0 1")
  .gain(0.08)
  .delay("0.04:0.125:0.05")

const percDust = s("perc_top*8")
  .n("0 ~ 1 ~ 0 ~ 1 ~")
  .gain("[0.05 0 0.08 0 0.05 0 0.09 0]")
  .delay("0.03:0.125:0.05")

const bassPocket = s("bass_tonal*8")
  .n("0 ~ 1 ~ 0 ~ 2 ~")
  .gain("[0.16 0 0.14 0 0.17 0 0.13 0]")
  .lpf(340)
  .room(0.04)

const bassReturn = s("bass_tonal*8")
  .n("0 ~ 1 2 0 ~ 2 1")
  .gain("[0.17 0 0.13 0.09 0.18 0 0.12 0.1]")
  .lpf(420)
  .room(0.04)

const bassBreak = s("bass_tonal*8")
  .n("0 ~ ~ ~ 1 ~ ~ ~")
  .gain("[0.08 0 0 0 0.07 0 0 0]")
  .lpf(260)

const stabMist = s("stab_tonal*8")
  .n("0 ~ 1 ~ 0 ~ 1 ~")
  .gain("[0.045 0 0.038 0 0.05 0 0.04 0]")
  .lpf(980)
  .delay("0.09:0.125:0.07")
  .room(0.24)

const stabPocket = s("stab_tonal*8")
  .n("0 0 1 ~ 0 1 0 ~")
  .gain("[0.05 0.025 0.042 0 0.048 0.03 0.04 0]")
  .lpf(sine.range(1100, 1800).slow(8))
  .delay("0.08:0.125:0.06")
  .room(0.18)

const pluckHook = s("pluck_tonal*16")
  .n("0 ~ 1 ~ 0 1 0 ~ 0 ~ 1 ~ 0 1 0 1")
  .gain("[0.025 0 0.05 0 0.03 0.055 0.035 0]*2")
  .lpf(sine.range(900, 2100).slow(8))
  .delay("0.1:0.125:0.08")

const pluckReturn = s("pluck_tonal*16")
  .n("0 1 0 1 0 1 0 ~ 0 1 0 1 0 1 0 1")
  .gain("[0.03 0.06 0.032 0.062]*4")
  .lpf(sine.range(1200, 2400).slow(8))
  .delay("0.08:0.125:0.08")

const vocalMist = s("vocal_chop*16")
  .n("0 1 2 1 0 1 3 1 0 1 2 1 0 4 3 1")
  .gain("[0.018 0.038 0.024 0.04]*4")
  .pan(sine.range(0.34, 0.66))
  .lpf(2300)

const vocalLift = s("vocal_chop*8")
  .n("0 2 1 3 0 2 4 1")
  .gain("[0.038 0.062 0.046 0.072]*2")
  .pan(sine.range(0.28, 0.72))
  .lpf(2800)

const air = s("air_texture")
  .slow(8)
  .gain(0.065)
  .room(0.88)
  .lpf(sine.range(700, 1700).slow(8))

const shimmer = s("shimmer_fx")
  .slow(8)
  .gain(0.022)

const impact = s("impact_wide ~ ~ ~")
  .slow(4)
  .gain(0.08)

stack(
  arrange(
    [8, silence],
    [16, kickPocket],
    [8, kickPocket.gain(0.92)],
    [8, silence],
    [16, kickReturn.gain(1.02)],
    [8, silence]
  ),

  arrange(
    [8, silence],
    [16, clapPocket],
    [8, clapPocket.gain(0.94)],
    [8, silence],
    [16, clapPocket.gain(1.04)],
    [8, silence]
  ),

  arrange(
    [8, hatsPocket.gain(0.36)],
    [16, hatsPocket],
    [8, hatsPocket.gain(0.92)],
    [8, silence],
    [16, hatsReturn.gain(0.94)],
    [8, hatsPocket.gain(0.26)]
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
    [8, silence],
    [16, percDust],
    [8, percDust.gain(0.86)],
    [8, silence],
    [16, percDust.gain(0.96)],
    [8, silence]
  ),

  arrange(
    [8, silence],
    [16, bassPocket],
    [8, bassPocket.gain(0.92)],
    [8, bassBreak],
    [16, bassReturn],
    [8, silence]
  ),

  arrange(
    [8, stabMist.gain(0.78)],
    [16, stabPocket],
    [8, pluckHook],
    [8, stabMist.gain(0.42)],
    [16, pluckReturn],
    [8, stabMist.gain(0.56)]
  ),

  arrange(
    [8, vocalMist.gain(0.62)],
    [16, vocalMist],
    [8, vocalLift],
    [8, vocalMist.gain(0.28)],
    [16, vocalLift.gain(1.04)],
    [8, silence]
  ),

  arrange(
    [8, air.gain(1.06)],
    [16, air.gain(0.08)],
    [8, shimmer.gain(0.05)],
    [8, air.gain(0.12)],
    [16, air.gain(0.08)],
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
