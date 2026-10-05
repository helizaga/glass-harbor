// @title Velvet Turnsignal
// @genre garage-pop / club crossover
// @bpm 130
// @details Pasteable song file for Strudel web. Run `glass-harbor song serve` before pasting. Hook-first, vocal-led, broken-grid club beat with a short breakdown and a clearer return than the recent deep-house drafts.
// @sections intro:8, groove:16, lift:8, breakdown:8, return:16, final-return:16, outro:8
// @section_roles intro:anchor, groove:groove, lift:lift, breakdown:breath, return:return, final-return:return, outro:outro

samples('http://localhost:5432')
setcpm(130 / 4)

const kick = s("kick_main")
  .n("<0 1 0 1>")
  .struct("x ~ ~ x ~ ~ x ~ x ~ ~ ~ x ~ ~ ~")
  .gain("[0.98 0 0 0.84 0 0 0.9 0 0.96 0 0 0 0.86 0 0 0]")

const clap = s("~ ~ clap_main ~ ~ clap_main ~ ~")
  .n("0 1")
  .gain("[0 0 0.24 0 0 0.28 0 0]")
  .clip(0.16)
  .room(0.08)

const hats = s("hat_closed*8")
  .n("0 1 0 2 0 1 0 3")
  .gain("[0.024 0.038 0.026 0.05]*2")
  .end("<0.05 0.07 0.06 0.08>*2")
  .swingBy(1 / 3, 4)
  .pan(sine.range(0.4, 0.6))

const hatsLift = s("hat_closed*16")
  .n("0 1 0 2 0 1 0 3 0 1 0 2 0 4 0 2")
  .gain("[0.028 0.046 0.03 0.058]*4")
  .end("<0.05 0.06 0.06 0.07>*4")
  .swingBy(1 / 4, 4)
  .pan(sine.range(0.34, 0.66))

const openHat = s("~ ~ hat_open ~ ~ ~ hat_open ~")
  .n("0 1")
  .gain(0.052)
  .clip(0.14)
  .end("<0.14 0.18>")

const percSkip = s("perc_top")
  .n(chooseCycles("0 1 0 2", "1 0 2 0"))
  .struct("~ x ~ ~ x ~ x ~")
  .degradeBy(0.14)
  .gain("[0 0.032 0 0 0.04 0 0.034 0]")
  .clip(0.1)
  .delay("0.05:0.125:0.06")

const bassGroove = note("<a1 ~ c2 ~ g1 ~ e2 ~>")
  .s("bass_pitched")
  .gain("[0.14 0 0.11 0 0.13 0 0.12 0]")
  .clip("<0.14 0.1 0.12 0.1>*2")
  .lpf(280)

const bassReturn = note("<a1 ~ c2 e2 g1 ~ e2 c2 ~>")
  .s("bass_pitched")
  .gain("[0.15 0 0.12 0.08 0.14 0 0.11 0]")
  .clip("<0.16 0.12 0.1 0.12>*2")
  .lpf(340)

const stabBed = "<Am7 Cmaj7 G6 Fmaj7>*2"
  .layer(
    x => x.voicing().note().s("stab_pitched").clip(0.22).gain(0.034).struct("x ~ ~ ~ x ~ ~ ~"),
    x => x.rootNotes(3).note().s("stab_pitched").clip(0.12).gain(0.018).struct("~ ~ x ~ ~ ~ x ~"),
  )
  .orbit(2)
  .lpf(1300)
  .room(0.18)

const stabLift = "<Am7 Cmaj7 G6 Fmaj7>*2"
  .layer(
    x => x.voicing().note().s("stab_pitched").clip(0.2).gain(0.04).struct("x ~ x ~ x ~ x ~"),
    x => x.rootNotes(3).note().s("stab_pitched").clip(0.1).gain(0.02).struct("~ x ~ ~ ~ x ~ ~"),
  )
  .orbit(2)
  .seg(8)
  .lpf(sine.range(1200, 1850).slow(8))
  .room(0.2)

const pluckHook = note("<a4 ~ c5 ~ e5 ~ c5 ~>")
  .s("pluck_pitched")
  .clip("<0.14 0.12 0.1 0.12>*2")
  .gain("[0.04 0 0.048 0 0.056 0 0.044 0]")
  .early("<0 0.012 0 0.016>*2")
  .orbit(3)
  .lpf(1650)
  .delay("0.18:0.125:0.14")
  .room(0.16)

const pluckAnswer = note("<e5 ~ g5 ~ a5 ~ g5 ~>")
  .s("pluck_pitched")
  .clip("<0.12 0.1 0.1 0.12>*2")
  .gain("[0.03 0 0.04 0 0.046 0 0.038 0]")
  .off(1 / 8, x => x.gain(0.45).lpf(1500).clip(0.08))
  .orbit(3)
  .lpf(1750)
  .delay("0.22:0.125:0.18")
  .room(0.18)

const vocalBed = s("vocal_chop*8")
  .n("<0 ~ 1 ~ 2 ~ 3 ~, 1 ~ 2 ~ 4 ~ 3 ~>")
  .gain("[0.018 0 0.022 0 0.026 0 0.022 0]")
  .clip("<0.12 0.16 0.14 0.18>*2")
  .end("<0.18 0.22 0.2 0.24>*2")
  .orbit(3)
  .lpf(1950)
  .pan(sine.range(0.36, 0.64))

const vocalHook = s("vocal_chop")
  .n("2")
  .slice(4, "<0 [1 2] 3 [2 1]>*2")
  .struct("x ~ ~ x ~ x ~ x")
  .lastOf(4, x => x.rev())
  .gain("[0.04 0 0 0.046 0 0.05 0 0.044]")
  .clip("<0.08 0.12 0.1 0.14>*2")
  .end(0.14)
  .orbit(3)
  .lpf(2350)
  .delay("0.08:0.125:0.05")

const vocalAnswer = s("vocal_chop*8")
  .n("<4 ~ ~ 1 3 ~ ~ 0, 3 ~ ~ 2 4 ~ ~ 1>")
  .gain("[0.03 0 0 0.036 0.034 0 0 0.038]")
  .clip("<0.09 0.12 0.1 0.13>*2")
  .orbit(3)
  .lpf(2100)
  .room(0.12)

const air = s("air_texture")
  .slow(8)
  .gain(0.026)
  .orbit(3)
  .lpf(sine.range(900, 1700).slow(8))
  .room(0.5)

const shimmer = s("shimmer_fx")
  .slow(8)
  .gain(0.024)
  .orbit(3)

const riser = s("riser_up")
  .slow(8)
  .gain(0.026)
  .orbit(3)

const impact = s("impact_wide ~ ~ ~")
  .slow(4)
  .gain(0.05)
  .orbit(3)

stack(
  arrange(
    [8, kick.gain(0.34)],
    [16, kick],
    [8, kick.gain(0.96)],
    [8, silence],
    [16, kick.gain(1.04)],
    [16, kick.gain(1.08)],
    [8, kick.gain(0.24)]
  ),

  arrange(
    [8, silence],
    [16, clap],
    [8, clap.gain(1.06)],
    [8, silence],
    [16, clap.gain(1.1)],
    [16, clap.gain(1.12)],
    [8, silence]
  ),

  arrange(
    [8, hats.gain(0.66)],
    [16, hats],
    [8, hatsLift],
    [8, hats.gain(0.42)],
    [16, hatsLift.gain(1.04)],
    [16, hatsLift.gain(1.08)],
    [8, hats.gain(0.34)]
  ),

  arrange(
    [8, silence],
    [16, openHat.gain(0.84)],
    [8, openHat],
    [8, silence],
    [16, openHat.gain(1.08)],
    [16, openHat.gain(1.12)],
    [8, silence]
  ),

  arrange(
    [8, silence],
    [16, percSkip],
    [8, percSkip.gain(1.06)],
    [8, silence],
    [16, percSkip.gain(1.1)],
    [16, percSkip.gain(1.12)],
    [8, silence]
  ),

  arrange(
    [8, silence],
    [16, bassGroove],
    [8, bassGroove.gain(1.02)],
    [8, bassGroove.gain(0.38)],
    [16, bassReturn],
    [16, bassReturn.gain(1.04)],
    [8, silence]
  ),

  arrange(
    [8, stabBed.gain(0.72)],
    [16, stabBed],
    [8, stabLift],
    [8, stabBed.gain(0.44)],
    [16, stabLift.gain(1.04)],
    [16, stabLift.gain(1.06)],
    [8, stabBed.gain(0.34)]
  ),

  arrange(
    [8, silence],
    [16, pluckHook.gain(0.84)],
    [8, pluckHook],
    [8, pluckHook.gain(0.46)],
    [16, pluckHook.gain(1.08)],
    [16, pluckHook.gain(1.04)],
    [8, silence]
  ),

  arrange(
    [8, silence],
    [16, silence],
    [8, pluckAnswer],
    [8, silence],
    [16, pluckAnswer.gain(1.08)],
    [16, pluckAnswer.gain(1.12)],
    [8, silence]
  ),

  arrange(
    [8, vocalBed.gain(0.86)],
    [16, vocalBed],
    [8, vocalBed.gain(1.04)],
    [8, vocalBed.gain(0.54)],
    [16, vocalBed.gain(1.08)],
    [16, vocalBed.gain(1.1)],
    [8, vocalBed.gain(0.44)]
  ),

  arrange(
    [8, silence],
    [16, vocalHook.gain(0.88)],
    [8, vocalHook],
    [8, silence],
    [16, vocalHook.gain(1.12)],
    [16, vocalHook.gain(1.16)],
    [8, silence]
  ),

  arrange(
    [8, silence],
    [16, silence],
    [8, vocalAnswer],
    [8, vocalAnswer.gain(0.44)],
    [16, vocalAnswer.gain(1.08)],
    [16, vocalAnswer.gain(1.12)],
    [8, silence]
  ),

  arrange(
    [8, air],
    [16, silence],
    [8, shimmer],
    [8, air.gain(0.8)],
    [16, shimmer.gain(1.04)],
    [16, shimmer.gain(1.06)],
    [8, air.gain(0.74)]
  ),

  arrange(
    [8, silence],
    [16, silence],
    [8, riser],
    [8, silence],
    [16, impact.gain(0.96)],
    [16, impact],
    [8, silence]
  )
)
