// @title Heatwave Switch
// @genre moombahton / global club crossover
// @bpm 102
// @details Pasteable Strudel song file for Strudel web. Run `glass-harbor song serve` before pasting. DJ Snake-adjacent club draft built around vocal punctuation, chest-forward percussion, and short bass answers instead of house pads or default browser synth leads.
// @sections intro:8, groove:16, lift:8, breakdown:8, return:16, outro:8
// @section_roles intro:anchor, groove:groove, lift:lift, breakdown:breath, return:return, outro:outro

samples('http://localhost:5432')
setcpm(102 / 4)

const kickIntro = s("kick_main*8")
  .n("0 1 0 1 0 1 0 1")
  .struct("x ~ ~ ~ x ~ ~ ~")
  .gain("[0.48 0 0 0 0.54 0 0 0]")

const kickGroove = s("kick_main*16")
  .n("0 1 0 1 0 1 0 1 0 1 0 1 0 1 0 1")
  .struct("x ~ ~ x ~ ~ x ~ x ~ ~ ~ x ~ x ~")
  .gain("[0.98 0 0 0.84 0 0 0.9 0 0.96 0 0 0 0.88 0 0.82 0]")

const clap = s("~ ~ clap_main ~ ~ clap_main ~ ~")
  .slow(2)
  .n("0 1")
  .gain("[0 0 0.28 0 0 0.32 0 0]")
  .clip(0.16)
  .room(0.06)

const hats = s("hat_closed*8")
  .n(chooseCycles("0 1 0 2 0 1 0 3", "1 0 2 0 1 0 3 0"))
  .struct("~ x ~ x x ~ x ~")
  .gain("[0 0.024 0 0.032 0.04 0 0.03 0]")
  .end("<0.05 0.07 0.06 0.08>*2")
  .swingBy(1 / 5, 4)
  .pan(sine.range(0.38, 0.62))

const percBody = s("perc_top*16")
  .n(chooseCycles("0 1 0 2 0 1 3 1 0 2 1 0 3 1 2 0", "1 0 2 1 0 3 1 0 2 1 0 3 1 2 0 1"))
  .struct("x ~ ~ x ~ x ~ ~ x ~ ~ x ~ x ~ ~")
  .degradeBy(0.08)
  .gain("[0.038 0 0 0.044 0 0.05 0 0 0.042 0 0 0.048 0 0.046 0 0]")
  .clip(0.1)
  .orbit(1)
  .delay("0.04:0.125:0.05")

const percLift = percBody
  .gain(1.08)
  .lastOf(4, x => x.off(1 / 16, y => y.gain(0.5).clip(0.08)))

const bassGroove = note("<f1 ~ ~ c2 ~ af1 ~ c2, f1 ~ c2 ~ ef2 ~ c2 ~>")
  .s("bass_pitched")
  .gain("[0.14 0 0 0.1 0 0.12 0 0.1]*2")
  .clip("<0.16 0.12 0.1 0.12>*2")
  .lpf(310)
  .orbit(2)

const bassLift = note("<f1 ~ c2 ~ ef2 ~ c2 ~, f1 ~ c2 ef2 ~ c2 ~ ~>")
  .s("bass_pitched")
  .gain("[0.15 0 0.11 0 0.12 0 0.1 0]*2")
  .clip("<0.16 0.12 0.1 0.11>*2")
  .lpf(340)
  .orbit(2)
  .lastOf(4, x => x.off(1 / 16, y => y.gain(0.42).clip(0.08)))

const bassBreak = note("<f1 ~ ~ ~ c2 ~ ~ ~>")
  .s("bass_pitched")
  .gain("[0.08 0 0 0 0.07 0 0 0]")
  .clip(0.12)
  .lpf(250)
  .orbit(2)

const vocalBed = s("vocal_chop*8")
  .n("<0 ~ 1 ~ 2 ~ 3 ~, 1 ~ 2 ~ 4 ~ 3 ~>")
  .gain("[0.018 0 0.022 0 0.024 0 0.02 0]")
  .clip("<0.12 0.16 0.14 0.18>*2")
  .end("<0.18 0.22 0.2 0.24>*2")
  .orbit(3)
  .lpf(1650)
  .pan(sine.range(0.34, 0.66))

const vocalHook = s("vocal_chop")
  .n("2")
  .slice(8, "<[3 5] ~ 2 ~ [4 6] ~ 1 ~>")
  .struct("~ x ~ ~ x ~ x ~")
  .lastOf(4, x => x.rev())
  .gain("[0 0.042 0 0 0.05 0 0.056 0]")
  .clip("<0.08 0.12 0.1 0.14>*2")
  .end(0.14)
  .off(1 / 8, x => x.gain(0.36).clip(0.06).lpf(2100))
  .orbit(3)
  .lpf(2250)
  .delay("0.08:0.125:0.05")

const vocalBreak = s("vocal_chop")
  .n("1")
  .slice(4, "<0 1 2 1>*2")
  .struct("x ~ ~ x ~ ~ x ~")
  .gain("[0.026 0 0 0.032 0 0 0.028 0]")
  .clip(0.1)
  .end(0.16)
  .orbit(3)
  .lpf(1850)

const riser = s("riser_up")
  .slow(8)
  .gain(0.018)
  .orbit(3)
  .end(0.4)
  .lpf(1800)

const impact = s("impact_wide ~ ~ ~")
  .slow(4)
  .gain(0.052)
  .clip(0.2)
  .orbit(3)

stack(
  arrange(
    [8, kickIntro],
    [16, kickGroove],
    [8, kickGroove.gain(0.98)],
    [8, silence],
    [16, kickGroove.gain(1.04)],
    [8, kickIntro.gain(0.28)]
  ),

  arrange(
    [8, silence],
    [16, clap],
    [8, clap.gain(1.04)],
    [8, silence],
    [16, clap.gain(1.08)],
    [8, silence]
  ),

  arrange(
    [8, hats.gain(0.58)],
    [16, hats],
    [8, hats.gain(1.08)],
    [8, silence],
    [16, hats.gain(1.12)],
    [8, hats.gain(0.42)]
  ),

  arrange(
    [8, percBody.gain(0.44)],
    [16, percBody],
    [8, percLift],
    [8, silence],
    [16, percLift.gain(1.06)],
    [8, percBody.gain(0.34)]
  ),

  arrange(
    [8, silence],
    [16, bassGroove],
    [8, bassLift],
    [8, bassBreak],
    [16, bassLift.gain(1.04)],
    [8, silence]
  ),

  arrange(
    [8, vocalBed.gain(0.72)],
    [16, vocalBed],
    [8, vocalBed.gain(0.92)],
    [8, vocalBreak],
    [16, vocalBed.gain(0.82)],
    [8, vocalBed.gain(0.54)]
  ),

  arrange(
    [8, silence],
    [16, silence],
    [8, vocalHook.gain(0.84)],
    [8, vocalBreak.gain(1.06)],
    [16, vocalHook],
    [8, silence]
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
