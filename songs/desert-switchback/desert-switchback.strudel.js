// @title Desert Switchback
// @genre festival trap / moombahton crossover
// @bpm 102
// @details Pasteable song file for Strudel web. Run `glass-harbor song serve` before pasting. Original DJ Snake-inspired club hybrid with syncopated reggaeton pull, sparse vocal punctuation, and a staged return built around the active runtime pack.
// @sections intro:4, groove:8, lift:4, breakdown:4, return:8, second-return:8, outro:4
// @section_roles intro:anchor, groove:groove, lift:lift, breakdown:breath, return:return, second-return:return, outro:outro

samples('http://localhost:5432')
setcpm(102 / 4)

const kickIntro = s("kick_main*4")
  .n("0 ~ ~ 1")
  .gain("[0.28 0 0 0.22]")
  .clip(0.18)

const kickGroove = s("kick_main*8")
  .n("0 ~ ~ 1 0 ~ 1 ~")
  .gain("[0.96 0 0 0.8 0.92 0 0.86 0]")
  .clip(0.16)

const kickReturn = s("kick_main*8")
  .n("0 ~ ~ 1 0 1 ~ 0")
  .gain("[1 0 0 0.84 0.96 0.76 0 0.82]")
  .clip(0.16)

const clapGroove = s("~ ~ clap_main ~ ~ ~ clap_main ~")
  .n("0 1")
  .gain(0.3)
  .clip(0.12)
  .room(0.08)

const clapReturn = clapGroove.gain(1.08)

const hatsTight = s("hat_closed*8")
  .n("0 ~ 1 ~ 0 ~ 2 1")
  .gain("[0.034 0 0.056 0 0.032 0 0.06 0.05]")
  .end("<0.05 0.05 0.06 0.05>*2")
  .pan(sine.range(0.42, 0.58))

const hatsDrive = s("hat_closed*16")
  .n("0 ~ 1 0 0 ~ 2 ~ 0 ~ 1 0 0 3 ~ 2")
  .gain("[0.034 0 0.056 0.04 0.032 0 0.064 0]*2")
  .end("<0.05 0.05 0.06 0.05>*4")
  .early("<0 0 0.008 0 0 0 0.012 0>*2")
  .pan(sine.range(0.38, 0.62))

const openHat = s("~ ~ ~ hat_open ~ ~ ~ hat_open")
  .n("0 1")
  .gain(0.048)
  .end("<0.12 0.1>")

const percSwing = s("perc_top*8")
  .n("<0 ~ 1 ~ 2 ~ ~ 1, 0 ~ 2 ~ 1 ~ ~ 2>")
  .gain("[0.026 0 0.042 0 0.036 0 0 0.044]")
  .clip(0.12)
  .early("<0 0.018 0 0.012>*2")
  .delay("0.02:0.125:0.03")

const bassPulse = s("bass_tonal*8")
  .n("0 ~ ~ 1 ~ ~ 2 ~")
  .gain("[0.164 0 0 0.102 0 0 0.118 0]")
  .clip(0.16)
  .lpf(280)

const bassLift = s("bass_tonal*8")
  .n("0 ~ ~ 1 0 ~ 2 ~")
  .gain("[0.148 0 0 0.098 0.154 0 0.124 0]")
  .clip(0.16)
  .lpf(320)

const bassBreak = s("bass_tonal*8")
  .n("0 ~ ~ ~ ~ ~ 1 ~")
  .gain("[0.1 0 0 0 0 0 0.084 0]")
  .clip(0.14)
  .lpf(240)

const stabAnswer = s("stab_tonal*8")
  .n("0 ~ ~ 1 ~ ~ 2 ~")
  .gain("[0.052 0 0 0.042 0 0 0.05 0]")
  .clip(0.22)
  .lpf(1500)
  .delay("0.04:0.125:0.04")
  .room(0.12)

const stabReturn = s("stab_tonal*8")
  .n("0 ~ 1 ~ 0 ~ 2 ~")
  .gain("[0.062 0 0.038 0 0.068 0 0.052 0]")
  .clip(0.22)
  .lpf(sine.range(1400, 2200).slow(8))
  .delay("0.05:0.125:0.05")
  .room(0.14)

const hookCall = note("<f4 ~ ab4 ~ c5 ~ ab4 ~>")
  .s("pluck_pitched")
  .gain("[0.028 0 0.044 0 0.056 0 0.042 0]")
  .clip("<0.12 0.16 0.14 0.18>*2")
  .end("<0.18 0.22 0.2 0.24>*2")
  .lpf(sine.range(1000, 1800).slow(8))
  .early("<0 0.012 0 0.008>*2")
  .delay("0.16:0.125:0.14")

const hookRush = note("<f4 ab4 ~ c5 f4 ab4 ~ c5 eb5>")
  .s("pluck_pitched")
  .gain("[0.03 0.048 0 0.066 0.032 0.052 0 0.074]")
  .clip("<0.12 0.15 0.1 0.16>*2")
  .end("<0.18 0.2 0.16 0.22>*2")
  .lpf(sine.range(1200, 2200).slow(8))
  .early("<0 0.01 0 0.014>*2")
  .delay("0.18:0.125:0.16")

const hookBed = chord("<fm7 ~ dbmaj7 ~ ebsus2 ~ c7 ~>")
  .slow(2)
  .voicing()
  .s("pluck_pitched")
  .gain(0.018)
  .clip(0.16)
  .end(0.2)
  .lpf(sine.range(900, 1500).slow(8))
  .delay("0.08:0.25:0.1")
  .room(0.16)

const vocalGhost = s("vocal_chop*8")
  .n("<0 ~ ~ 1 2 ~ ~ 1, 0 ~ ~ 2 3 ~ ~ 2>")
  .gain("[0.014 0 0 0.028 0.022 0 0 0.03]")
  .clip("<0.1 0.14 0.12 0.16>*2")
  .end("<0.18 0.22 0.2 0.24>*2")
  .lpf(1900)
  .pan(sine.range(0.34, 0.66))

const vocalLead = s("vocal_chop*8")
  .n("<0 2 ~ 1 3 ~ 2 ~, 1 3 ~ 2 4 ~ 0 ~>")
  .gain("[0.042 0.06 0 0.048 0.068 0 0.054 0]")
  .clip("<0.1 0.14 0.12 0.16>*2")
  .end("<0.16 0.2 0.18 0.22>*2")
  .early("<0 0.02 0 0.012>*2")
  .lpf(2350)
  .pan(sine.range(0.28, 0.72))

const vocalBreak = s("vocal_chop*4")
  .n("0 ~ 2 ~")
  .gain("[0.03 0 0.044 0]")
  .clip(0.1)
  .end(0.18)
  .lpf(2100)

const air = s("air_texture")
  .slow(8)
  .gain(0.03)
  .room(0.64)
  .lpf(sine.range(700, 1500).slow(8))

const shimmer = s("shimmer_fx")
  .slow(8)
  .gain(0.024)
  .clip(0.28)

const riser = s("riser_up")
  .slow(8)
  .gain(0.04)
  .clip(0.34)

const impact = s("impact_wide ~ ~ ~")
  .slow(4)
  .gain(0.086)
  .clip(0.24)

stack(
  arrange(
    [4, kickIntro],
    [8, kickGroove],
    [4, kickGroove.gain(1.02)],
    [4, kickIntro.gain(0.7)],
    [8, kickReturn],
    [8, kickReturn.gain(1.04)],
    [4, kickIntro.gain(0.22)]
  ),

  arrange(
    [4, silence],
    [8, clapGroove],
    [4, clapGroove.gain(0.92)],
    [4, silence],
    [8, clapReturn],
    [8, clapReturn.gain(1.06)],
    [4, silence]
  ),

  arrange(
    [4, hatsTight.gain(0.4)],
    [8, hatsTight],
    [4, hatsDrive.gain(0.9)],
    [4, silence],
    [8, hatsDrive],
    [8, hatsDrive.gain(1.08)],
    [4, hatsTight.gain(0.3)]
  ),

  arrange(
    [4, silence],
    [8, openHat.gain(0.6)],
    [4, openHat],
    [4, silence],
    [8, openHat.gain(1.04)],
    [8, openHat.gain(1.08)],
    [4, silence]
  ),

  arrange(
    [4, percSwing.gain(0.34)],
    [8, percSwing],
    [4, percSwing.gain(1.04)],
    [4, silence],
    [8, percSwing.gain(1.08)],
    [8, percSwing.gain(1.12)],
    [4, percSwing.gain(0.24)]
  ),

  arrange(
    [4, silence],
    [8, bassPulse],
    [4, bassLift.gain(0.9)],
    [4, bassBreak],
    [8, bassLift],
    [8, bassLift.gain(1.08)],
    [4, silence]
  ),

  arrange(
    [4, silence],
    [8, stabAnswer.gain(0.54)],
    [4, stabAnswer],
    [4, silence],
    [8, stabReturn],
    [8, stabReturn.gain(1.08)],
    [4, silence]
  ),

  arrange(
    [4, hookCall.gain(0.56)],
    [8, hookCall],
    [4, hookRush.gain(0.82)],
    [4, hookCall.gain(0.26)],
    [8, hookRush],
    [8, hookRush.gain(1.04)],
    [4, hookCall.gain(0.3)]
  ),

  arrange(
    [4, hookBed.gain(0.34)],
    [8, silence],
    [4, hookBed.gain(0.4)],
    [4, hookBed.gain(0.24)],
    [8, silence],
    [8, hookBed.gain(0.42)],
    [4, hookBed.gain(0.3)]
  ),

  arrange(
    [4, vocalGhost.gain(0.5)],
    [8, vocalGhost],
    [4, vocalGhost.gain(0.8)],
    [4, vocalBreak],
    [8, vocalLead],
    [8, vocalLead.gain(1.08)],
    [4, vocalGhost.gain(0.34)]
  ),

  arrange(
    [4, air.gain(0.9)],
    [8, silence],
    [4, shimmer.gain(0.8)],
    [4, air.gain(0.7)],
    [8, silence],
    [8, silence],
    [4, air.gain(0.7)]
  ),

  arrange(
    [4, silence],
    [8, silence],
    [4, riser.gain(0.9)],
    [4, silence],
    [8, impact],
    [8, impact.gain(1.08)],
    [4, silence]
  )
)
