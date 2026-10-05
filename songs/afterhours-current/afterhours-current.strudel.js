// @title Afterhours Current
// @genre atmospheric deep house
// @bpm 122
// @details Pasteable song file for Strudel web. Run `glass-harbor song serve` before pasting. Late-night radio deep-house beat with patient intro, airy breakdown, and two blooming returns shaped around the active KSHMR-backed runtime pack.
// @sections intro:8, groove:16, lift:8, breakdown:16, return:16, breath:8, final-return:16, outro:8
// @section_roles intro:anchor, groove:groove, lift:lift, breakdown:breath, return:return, breath:breath, final-return:return, outro:outro

samples('http://localhost:5432')
setcpm(122 / 4)

const kick = s("kick_main*4")
  .n("0 1 0 1")
  .gain("[0.9 0.82 0.88 0.8]")

const clap = s("~ clap_main ~ clap_main")
  .n("0 1")
  .gain(0.28)
  .room(0.12)

const hatsSoft = s("hat_closed*8")
  .n("0 1 0 2 0 1 0 3")
  .gain("[0.03 0.05 0.034 0.058]*2")
  .end("<0.08 0.06 0.09 0.07>*2")
  .swingBy(1 / 6, 4)
  .pan(sine.range(0.42, 0.58))

const hatsFull = s("hat_closed*16")
  .n("0 1 0 2 0 1 0 3 0 1 0 2 0 4 0 2")
  .gain("[0.04 0.06 0.042 0.072]*4")
  .end("<0.07 0.06 0.08 0.07>*4")
  .swingBy(1 / 3, 4)
  .pan(sine.range(0.36, 0.64))

const openHat = s("~ hat_open ~ ~ ~ hat_open ~ ~")
  .n("0 1")
  .gain(0.05)
  .end("<0.22 0.18>")
  .delay("0.16:0.125:0.12")

const percDust = s("perc_top")
  .n("<0 1 0 1, 1 0 1 0>")
  .struct("~ ~ x ~ x ~ x ~")
  .degradeBy(0.12)
  .gain("[0.028 0.036 0.03 0.034]")
  .clip(0.12)
  .delay("0.02:0.125:0.03")

const subVerse = note("<a1 ~ c2 ~ a1 ~ e2 ~>")
  .s("bass_pitched")
  .gain("[0.11 0 0.1 0 0.118 0 0.102 0]")
  .clip("<0.16 0.14 0.15 0.13>*2")
  .lpf(260)
  .room(0.03)

const subDrop = note("<a1 ~ c2 e2 a1 ~ e2 c2>")
  .s("bass_pitched")
  .gain("[0.118 0 0.102 0.072 0.126 0 0.108 0.078]")
  .clip("<0.16 0.14 0.12 0.15>*2")
  .lpf(320)
  .room(0.03)

const subBreak = note("<a1 ~ ~ ~ c2 ~ ~ ~>")
  .s("bass_pitched")
  .gain("[0.075 0 0 0 0.07 0 0 0]")
  .clip(0.14)
  .lpf(230)

const harmonyFrame = "<Am9 Fmaj7 Cmaj9 G6>*2"

const padIntro = harmonyFrame
  .layer(
    x => x.struct("[~ x]*2").voicing().note().s("stab_pitched").clip(0.82).gain(0.034),
    x => x.rootNotes(3).note().s("stab_pitched").clip(0.16).gain(0.014).struct("x ~ ~ ~ x ~ ~ ~"),
  )
  .orbit(2)
  .lpf(1050)
  .delay("0.08:0.25:0.16")
  .room(0.46)

const padFull = harmonyFrame
  .layer(
    x => x.struct("[~ x]*2").voicing().note().s("stab_pitched").clip(0.92).gain(0.042),
    x => x.rootNotes(3).note().s("stab_pitched").clip(0.18).gain(0.016).struct("x ~ ~ ~ x ~ ~ ~"),
  )
  .orbit(2)
  .seg(16)
  .lpf(sine.range(980, 1800).slow(16))
  .delay("0.08:0.25:0.2")
  .room(0.54)

const padBreak = "<Am9 Fmaj7 Cmaj9 G6>*2"
  .struct("x ~ x ~")
  .layer(
    x => x.voicing().note().s("stab_pitched").clip(0.72).gain(0.044),
    x => x.rootNotes(3).note().s("stab_pitched").clip(0.14).gain(0.012).struct("x ~ ~ ~"),
  )
  .slow(4)
  .orbit(2)
  .seg(12)
  .lpf(sine.range(1200, 2100).slow(12))
  .delay("0.1:0.25:0.22")
  .room(0.6)

const pluck = note("<a3 ~ c4 ~ e4 ~ c4 ~ a3 ~ c4 ~ e4 ~ g4 ~>")
  .s("pluck_pitched")
  .clip("<0.18 0.14 0.12 0.16>*4")
  .gain("[0.024 0 0.034 0 0.042 0 0.032 0]*2")
  .orbit(3)
  .lpf(sine.range(950, 1700).slow(8))
  .early("<0 0.01 0 0.015>*4")
  .delay("0.22:0.125:0.18")
  .room(0.2)

const pluckBloom = note("<a3 ~ c4 ~ e4 ~ g4 ~ a3 ~ e4 ~ g4 ~ c4 ~>")
  .s("pluck_pitched")
  .clip("<0.2 0.16 0.14 0.18>*4")
  .gain("[0.03 0 0.042 0 0.052 0 0.06 0]*2")
  .orbit(3)
  .early("<0 0.015 0 0.01>*4")
  .lpf(sine.range(1150, 2100).slow(8))
  .delay("0.24:0.125:0.22")
  .room(0.24)
  .off(1 / 8, x => x.gain(0.42).clip(0.1).lpf(1350))

const vocalMist = s("vocal_chop*8")
  .n("<0 ~ 1 ~ 2 ~ 3 ~, 1 ~ 2 ~ 3 ~ 4 ~>")
  .gain("[0.02 0 0.03 0 0.024 0 0.034 0]")
  .clip("<0.16 0.22 0.14 0.18>*2")
  .end("<0.28 0.34 0.24 0.3>*2")
  .orbit(3)
  .lpf(1900)
  .early("<0 0.01 0 0.015>*2")
  .pan(sine.range(0.34, 0.66))

const vocalAccent = s("vocal_chop*8")
  .n("<0 2 ~ 1 3 ~ 2 4, 1 3 ~ 2 4 ~ 0 2>")
  .gain("[0.026 0.04 0 0.032 0.044 0 0.036 0.048]")
  .clip("<0.12 0.16 0.1 0.14>*2")
  .end("<0.22 0.28 0.18 0.24>*2")
  .orbit(3)
  .early("<0 0.02 0 0.01>*2")
  .lpf(2300)
  .pan(sine.range(0.28, 0.72))

const vocalSlice = s("vocal_chop")
  .n("1")
  .slice(4, "<0 [1 2] 3 [2 1]>*2")
  .struct("~ x ~ x x ~ x ~")
  .lastOf(4, x => x.rev())
  .clip("<0.12 0.16 0.14 0.18>*2")
  .end(0.16)
  .gain("[0 0.026 0 0.032 0.038 0 0.03 0]")
  .orbit(3)
  .lpf(2100)
  .delay("0.12:0.125:0.08")

const leadHint = note("<a3 ~ c4 ~ e4 ~ g4 ~>")
  .s("pluck_pitched")
  .clip(0.14)
  .gain(0.03)
  .orbit(3)
  .lpf(1500)
  .delay("0.34:0.125:0.24")
  .room(0.5)

const leadBreak = note("<a3 ~ c4 ~ e4 ~ g4 ~ c4 ~ e4 ~ g4 ~ a3 ~>")
  .s("pluck_pitched")
  .clip(0.18)
  .gain(0.04)
  .orbit(3)
  .lpf(1700)
  .delay("0.38:0.125:0.28")
  .room(0.56)

const arp = note("<a3 c4 e4 c4 g4 c4 e4 c5>")
  .s("pluck_pitched")
  .clip(0.12)
  .gain(0.03)
  .orbit(3)
  .lpf(sine.range(1200, 2200).slow(8))
  .delay("0.22:0.125:0.18")
  .room(0.18)

const air = s("air_texture")
  .slow(8)
  .gain(0.034)
  .orbit(3)
  .room(0.7)
  .lpf(sine.range(850, 1700).slow(8))

const shimmer = s("shimmer_fx")
  .slow(8)
  .orbit(3)
  .gain(0.03)

const riser = s("riser_up")
  .slow(8)
  .orbit(3)
  .gain(0.034)

const impact = s("impact_wide ~ ~ ~")
  .slow(4)
  .orbit(3)
  .gain(0.062)

stack(
  arrange(
    [8, kick.gain(0.18)],
    [16, kick],
    [8, kick.gain(0.96)],
    [16, silence],
    [16, kick.gain(1.02)],
    [8, silence],
    [16, kick.gain(1.04)],
    [8, kick.gain(0.16)]
  ),

  arrange(
    [8, silence],
    [16, clap],
    [8, clap.gain(0.9)],
    [16, silence],
    [16, clap.gain(1.02)],
    [8, silence],
    [16, clap.gain(1.04)],
    [8, silence]
  ),

  arrange(
    [8, hatsSoft.gain(0.7)],
    [16, hatsSoft],
    [8, hatsFull],
    [16, hatsSoft.gain(0.76)],
    [16, hatsFull.gain(0.94)],
    [8, hatsSoft.gain(0.68)],
    [16, hatsFull.gain(1.02)],
    [8, hatsSoft.gain(0.54)]
  ),

  arrange(
    [8, silence],
    [16, openHat],
    [8, openHat.gain(1.04)],
    [16, silence],
    [16, openHat.gain(1.08)],
    [8, silence],
    [16, openHat.gain(1.12)],
    [8, silence]
  ),

  arrange(
    [8, percDust.gain(0.4)],
    [16, percDust],
    [8, percDust.gain(1.06)],
    [16, silence],
    [16, percDust.gain(1.08)],
    [8, silence],
    [16, percDust.gain(1.12)],
    [8, percDust.gain(0.32)]
  ),

  arrange(
    [8, silence],
    [16, subVerse],
    [8, subVerse.gain(1.04)],
    [16, subBreak],
    [16, subDrop],
    [8, silence],
    [16, subDrop.gain(1.08)],
    [8, silence]
  ),

  arrange(
    [8, padIntro],
    [16, padFull],
    [8, padFull.gain(1.06)],
    [16, padBreak],
    [16, padFull.gain(1.04)],
    [8, padIntro.gain(0.92)],
    [16, padFull.gain(1.08)],
    [8, padIntro.gain(0.78)]
  ),

  arrange(
    [8, silence],
    [16, pluck.gain(0.84)],
    [8, pluck.gain(0.96)],
    [16, silence],
    [16, pluckBloom],
    [8, silence],
    [16, pluckBloom.gain(1.08)],
    [8, silence]
  ),

  arrange(
    [8, vocalMist.gain(0.82)],
    [16, vocalMist],
    [8, vocalAccent.gain(0.86)],
    [16, vocalMist.gain(0.7)],
    [16, vocalAccent],
    [8, vocalMist.gain(0.62)],
    [16, vocalAccent.gain(1.04)],
    [8, vocalMist.gain(0.5)]
  ),

  arrange(
    [8, silence],
    [16, silence],
    [8, vocalSlice.gain(0.82)],
    [16, silence],
    [16, vocalSlice],
    [8, silence],
    [16, vocalSlice.gain(1.06)],
    [8, silence]
  ),

  arrange(
    [8, silence],
    [16, silence],
    [8, leadHint],
    [16, leadBreak],
    [16, leadBreak.gain(0.92)],
    [8, silence],
    [16, arp.gain(1.1)],
    [8, silence]
  ),

  arrange(
    [8, air.gain(0.8)],
    [16, air],
    [8, shimmer.gain(0.9)],
    [16, air.gain(1.08)],
    [16, silence],
    [8, air.gain(0.72)],
    [16, riser.gain(0.88)],
    [8, air.gain(0.56)]
  ),

  arrange(
    [8, silence],
    [16, silence],
    [8, silence],
    [16, silence],
    [16, impact],
    [8, silence],
    [16, impact.gain(1.06)],
    [8, silence]
  )
)
