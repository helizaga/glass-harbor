// @title Venom Arc Lights
// @genre moombahton / global club
// @bpm 104
// @details Pasteable song file for Strudel web. Run `glass-harbor song serve` before pasting. DJ Snake-adjacent club record built around a sliced vocal slogan, broken percussion, lean kick-and-bass tradeoffs, and staged return pressure instead of house-pad bloom.
// @sections intro:4, groove:8, lift:4, breakdown:4, return:8, second-return:8, outro:4
// @section_roles intro:anchor, groove:groove, lift:lift, breakdown:breath, return:return, second-return:return, outro:outro

samples('http://localhost:5432')
setcpm(104 / 4)

const kickIntro = s("kick_main*8")
  .struct("x ~ ~ ~ ~ ~ x ~")
  .n("0 1")
  .gain("[0.42 0 0 0 0 0 0.3 0]")
  .clip(0.16)
  .orbit(0)

const kickGroove = s("kick_main*16")
  .struct("x ~ ~ ~ x ~ ~ x ~ ~ x ~ ~ x ~ ~")
  .n("0 1 0 0 1")
  .gain("[0.96 0 0 0 0.82 0 0 0.74 0 0 0.86 0 0 0.78 0 0]")
  .clip(0.16)
  .orbit(0)

const kickReturn = s("kick_main*16")
  .struct("x ~ ~ ~ x ~ x ~ ~ ~ x ~ x ~ ~ ~")
  .n("0 1 0 1 0")
  .gain("[1 0 0 0 0.84 0 0.74 0 0 0 0.92 0 0.78 0 0 0]")
  .clip(0.16)
  .orbit(0)

const clapGroove = s("~ ~ clap_main ~ ~ ~ clap_main ~")
  .n("0 1")
  .gain(0.24)
  .clip(0.12)
  .room(0.08)
  .orbit(0)

const clapReturn = clapGroove.gain(1.1)

const hatsNeedle = s("hat_closed*16")
  .n("0 ~ 1 ~ 0 ~ ~ 2 0 ~ 1 ~ 0 ~ 3 ~")
  .gain("[0.022 0 0.036 0 0.024 0 0 0.042 0.024 0 0.038 0 0.026 0 0.046 0]")
  .end("<0.04 0.05 0.04 0.06>*4")
  .late("<0 0.008 0 0.012>*4")
  .orbit(0)

const hatsDrive = s("hat_closed*16")
  .n("0 ~ 1 0 0 ~ 2 ~ 0 ~ 1 0 0 ~ 3 ~")
  .gain("[0.026 0 0.04 0.03 0.024 0 0.046 0 0.026 0 0.042 0.032 0.024 0 0.05 0]")
  .end("<0.04 0.05 0.04 0.06>*4")
  .late("<0 0.01 0 0.012>*4")
  .orbit(0)

const percSpine = s("perc_top")
  .n("<0 1 2 1, 1 0 2 0>")
  .struct("x ~ x ~ ~ x ~ x")
  .degradeBy(0.1)
  .gain("[0.056 0 0.062 0 0 0.072 0 0.064]")
  .clip(0.12)
  .early("<0 0.012 0 0.018>*2")
  .delay("0.03:0.125:0.04")
  .orbit(0)

const percReturn = s("perc_top")
  .n("<0 2 1 2, 1 0 2 1>")
  .struct("x ~ x x ~ x ~ x")
  .gain("[0.062 0 0.076 0.064 0 0.082 0 0.074]")
  .clip(0.12)
  .early("<0 0.014 0.008 0>*2")
  .delay("0.03:0.125:0.05")
  .orbit(0)

const bassLean = note("<f1 ~ ~ c2 ~ ~ eb2 ~>")
  .s("bass_pitched")
  .gain("[0.128 0 0 0.102 0 0 0.116 0]")
  .clip("<0.16 0.12 0.14 0.12>*2")
  .lpf(300)
  .room(0.02)
  .orbit(1)

const bassLift = note("<f1 ~ ~ c2 f1 ~ eb2 ~>")
  .s("bass_pitched")
  .gain("[0.12 0 0 0.098 0.132 0 0.12 0]")
  .clip("<0.14 0.12 0.12 0.1>*2")
  .lpf(320)
  .room(0.02)
  .orbit(1)

const bassReturn = note("<f1 ~ c2 ~ f1 ~ eb2 c2>")
  .s("bass_pitched")
  .gain("[0.14 0 0.108 0 0.146 0 0.126 0.092]")
  .clip("<0.16 0.12 0.14 0.1>*2")
  .lpf(340)
  .room(0.03)
  .orbit(1)

const bassBreak = note("<f1 ~ ~ ~ ~ ~ c2 ~>")
  .s("bass_pitched")
  .gain("[0.09 0 0 0 0 0 0.076 0]")
  .clip(0.12)
  .lpf(250)
  .orbit(1)

const vocalGhost = s("vocal_chop")
  .n("1")
  .slice(4, "<0 [1 2] 3 [2 1]>*2")
  .struct("x ~ ~ x x ~ x ~")
  .clip("<0.12 0.16 0.14 0.18>*2")
  .end(0.16)
  .gain("[0.028 0 0 0.04 0.046 0 0.038 0]")
  .lpf(2200)
  .orbit(2)

const vocalLead = s("vocal_chop")
  .n("2")
  .slice(4, "<0 1 [2 3] 1>*2")
  .struct("x ~ x ~ x ~ ~ x")
  .lastOf(4, x => x.rev())
  .clip("<0.12 0.14 0.16 0.14>*2")
  .end(0.16)
  .gain("[0.05 0 0.064 0 0.07 0 0 0.058]")
  .early("<0 0.014 0.008 0>*2")
  .lpf(2450)
  .delay("0.08:0.125:0.06")
  .orbit(2)

const vocalBreak = s("vocal_chop")
  .n("3")
  .slice(2, "<0 1 0 1>")
  .struct("x ~ ~ x")
  .clip(0.14)
  .end(0.16)
  .gain("[0.042 0 0 0.052]")
  .lpf(2100)
  .orbit(2)

const riser = s("riser_up")
  .slow(8)
  .gain(0.024)
  .clip(0.22)
  .orbit(2)

const impact = s("impact_wide ~ ~ ~")
  .slow(4)
  .gain(0.08)
  .clip(0.2)
  .orbit(2)

stack(
  arrange(
    [4, kickIntro],
    [8, kickGroove],
    [4, kickGroove.gain(1.02)],
    [4, kickIntro.gain(0.62)],
    [8, kickReturn],
    [8, kickReturn.gain(1.06)],
    [4, kickIntro.gain(0.2)]
  ),

  arrange(
    [4, silence],
    [8, clapGroove],
    [4, clapGroove.gain(0.94)],
    [4, silence],
    [8, clapReturn],
    [8, clapReturn.gain(1.04)],
    [4, silence]
  ),

  arrange(
    [4, hatsNeedle.gain(0.4)],
    [8, hatsNeedle],
    [4, hatsDrive.gain(0.92)],
    [4, silence],
    [8, hatsDrive],
    [8, hatsDrive.gain(1.04)],
    [4, hatsNeedle.gain(0.28)]
  ),

  arrange(
    [4, percSpine.gain(0.48)],
    [8, percSpine],
    [4, percSpine.gain(1.08)],
    [4, silence],
    [8, percReturn],
    [8, percReturn.gain(1.08)],
    [4, percSpine.gain(0.24)]
  ),

  arrange(
    [4, silence],
    [8, bassLean],
    [4, bassLift],
    [4, bassBreak],
    [8, bassReturn],
    [8, bassReturn.gain(1.08)],
    [4, silence]
  ),

  arrange(
    [4, vocalGhost.gain(0.64)],
    [8, vocalGhost],
    [4, vocalLead.gain(0.84)],
    [4, vocalBreak],
    [8, vocalLead],
    [8, vocalLead.gain(1.08)],
    [4, vocalGhost.gain(0.34)]
  ),

  arrange(
    [4, silence],
    [8, silence],
    [4, riser.gain(0.8)],
    [4, silence],
    [8, impact.gain(0.96)],
    [8, impact.gain(1.02)],
    [4, silence]
  )
)
