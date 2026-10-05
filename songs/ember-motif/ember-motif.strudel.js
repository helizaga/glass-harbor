// @title Ember Motif
// @genre motif-led downtempo club pop
// @bpm 98
// @details Pasteable Strudel song file for Strudel web. Run `glass-harbor song serve` before pasting. Motif-first arrangement inspired by the user-provided reference: repeating lead memory, answer phrase, layered bass/sub pocket, restrained first half, and a larger final return.
// @sections intro:4, groove:8, lift:8, return:8, breakdown:4, final-return:8, outro:4
// @section_roles intro:anchor, groove:groove, lift:lift, return:return, breakdown:breath, final-return:return, outro:outro

samples('http://localhost:5432')
setcpm(98 / 4)

const motifNotes = arrange(
  [3, "<[f4 ~ ab4 ~] [c5 ~ ab4 ~] [g4 ~ f4 ~] [eb4 ~ ~ ~]>*2"],
  [1, "<[g4 ~ bb4 ~] [d5 ~ bb4 ~] [c5 ~ g4 ~] [f4 ~ ~ ~]>*2"],
)
  .note()

const motif = motifNotes
  .s("pluck_pitched")
  .clip("<0.12 0.14 0.1 0.16>*2")
  .gain("<0.18 0.22 0.2 0.24>")
  .lpf("<900 1100 1350 1200>")
  .delay("0.18:0.25:0.14")
  .room(0.08)
  .orbit(2)

const motifBig = motif
  .lpf("<1600 1900 2300 2100>")
  .gain(0.3)

const motifTop = motif
  .fast(2)
  .clip(0.08)
  .gain(0.042)
  .mask("<0 1 0 1 0 1 1 1>")

const answer = arrange(
  [4, "<[~ ~ c5 ~] [~ eb5 ~ ~] [~ c5 ~ g4] [~ ~ ~ ~]>*2"],
)
  .note()
  .s("pluck_pitched")
  .clip("<0.1 0.12 0.12 0.14>*2")
  .gain(0.082)
  .lpf(1550)
  .delay("0.14:0.25:0.11")
  .room(0.24)
  .orbit(2)

const chords = "<Fm9 Dbmaj7 Abadd9 Cm7>*2"
  .layer(
    x => x.voicing().note().s("pluck_pitched").clip(0.34).gain(0.042).struct("x ~ ~ ~ x ~ ~ ~"),
    x => x.rootNotes(3).note().s("pluck_pitched").clip(0.14).gain(0.016).struct("~ ~ x ~ ~ ~ x ~"),
  )
  .orbit(2)
  .lpf(1200)
  .room(0.16)

const punch = arrange(
  [4, "<[f4 ab4 c5] ~ [eb4 g4 bb4] ~ [c4 eb4 g4] ~ [bb3 d4 f4] ~>*2"],
)
  .note()
  .s("pluck_pitched")
  .clip(0.12)
  .gain(0.064)
  .lpf(1450)
  .room(0.08)
  .orbit(2)

const bass = arrange(
  [2, "<[f2 ~] [~ ~ f2 g2] [~ c2] [~ ~]>*4"],
  [1, "<[f2 ~] [~ ~ f2 g2] [~ c2] [f2 f2 ~ ~]>*4"],
  [1, "<[ab2 ~] [ab2 ~ bb2 c3] [~ eb2] [~ ~]>*4"],
)
  .note()
  .s("bass_pitched")
  .clip("<0.16 0.12 0.14 0.1>*4")
  .gain(0.28)
  .lpf(360)
  .orbit(1)

const sub = bass
  .transpose(-12)
  .clip(0.18)
  .lpf(220)
  .gain(0.24)

const bassFill = arrange(
  [1, "<[f2 ~] [~ ~ f2 g2] [~ c2] [f2 f2 f2 ~]>*4"],
  [1, "<[f2 f2] [~ ~ f2 g2] [~ c2] [~ ~]>*4"],
  [1, "<[ab2 ~] [ab2 ~ bb2 c3] [~ eb2] [~ ~]>*4"],
)
  .note()
  .s("bass_pitched")
  .clip("<0.16 0.12 0.14 0.1>*4")
  .gain(0.31)
  .lpf(420)
  .orbit(1)

const subFill = bassFill
  .transpose(-12)
  .clip(0.18)
  .lpf(240)
  .gain(0.26)

const kick = arrange(
  [4, "<[kick_main ~] [~ ~ kick_main ~] [kick_main ~] [~ kick_main ~ ~]>*2"],
)
  .gain(1.02)
  .orbit(0)

const clap = arrange(
  [4, "<[~ ~ clap_main ~] [~ ~ ~ ~] [~ ~ clap_main ~] [~ ~ ~ ~]>*2"],
)
  .gain(0.42)
  .clip(0.14)
  .orbit(0)

const snare = arrange(
  [4, "<[~ ~ clap_main ~] [~ ~ clap_main ~] [~ ~ clap_main ~] [~ ~ clap_main ~]>*2"],
)
  .gain(0.22)
  .clip(0.08)
  .room(0.04)
  .orbit(0)

const hats = arrange(
  [4, "<[hat_closed ~ hat_closed ~] [hat_closed hat_closed ~ hat_closed] [hat_closed ~ hat_closed ~] [hat_closed ~ hat_closed hat_closed]>*2"],
)
  .gain("<0.08 0.11 0.09 0.13>")
  .end("<0.05 0.06 0.05 0.07>*2")
  .late("<0 0.008 0 0.012>*2")
  .orbit(0)

const hatLift = arrange(
  [4, "<[hat_closed*4] [hat_closed*4] [hat_closed*4] [hat_closed*8]>*2"],
)
  .gain("<0.07 0.08 0.1 0.14>")
  .end(0.04)
  .orbit(0)

const perc = arrange(
  [4, "<[~ perc_top ~ ~] [perc_top ~ ~ ~] [~ perc_top ~ perc_top] [~ ~ ~ ~]>*2"],
)
  .gain(0.12)
  .clip(0.1)
  .degradeBy(0.08)
  .orbit(0)

const fill = arrange(
  [3, s("~")],
  [1, s("<~ ~ perc_top perc_top perc_top shimmer_fx>").gain(0.12).clip(0.1)],
)
  .orbit(0)

const air = s("air_texture")
  .slow(8)
  .lpf(1200)
  .gain(0.028)
  .orbit(3)

const sparkle = s("shimmer_fx")
  .slow(8)
  .lpf(2800)
  .gain(0.022)
  .orbit(3)

const rev = s("riser_up")
  .slow(4)
  .clip(0.2)
  .gain(0.026)
  .orbit(3)

const impact = s("impact_wide ~ ~ ~")
  .slow(4)
  .clip(0.18)
  .gain(0.04)
  .orbit(3)

stack(
  arrange(
    [4, motif.lpf(520).gain(0.16)],
    [8, motif.lpf(760).gain(0.22)],
    [8, motif.lpf("<900 1100 1400 1800>").gain(0.24)],
    [8, motifBig],
    [4, motif.lpf(680).gain(0.18)],
    [8, motifBig],
    [4, motif.lpf(540).gain(0.14)]
  ),

  arrange(
    [4, silence],
    [8, silence],
    [8, answer],
    [8, answer.gain(1.08)],
    [4, answer.gain(0.9)],
    [8, answer.gain(1.22)],
    [4, silence]
  ),

  arrange(
    [4, chords.lpf(840).gain(0.72)],
    [8, chords.gain(0.84)],
    [8, chords.gain(0.96)],
    [8, chords.gain(1.02)],
    [4, chords.lpf(1000).gain(0.82)],
    [8, chords.gain(1.1)],
    [4, chords.gain(0.6)]
  ),

  arrange(
    [4, silence],
    [8, silence],
    [8, silence],
    [8, punch],
    [4, silence],
    [8, punch.gain(1.16)],
    [4, silence]
  ),

  arrange(
    [4, silence],
    [8, bass.gain(0.94)],
    [8, bass],
    [8, bassFill],
    [4, bass.lpf("<360 300 260 220>").gain(0.76)],
    [8, bassFill.gain(1.06)],
    [4, silence]
  ),

  arrange(
    [4, silence],
    [8, sub.gain(0.88)],
    [8, sub],
    [8, subFill],
    [4, sub.lpf("<220 190 170 150>").gain(0.72)],
    [8, subFill.gain(1.08)],
    [4, silence]
  ),

  arrange(
    [4, silence],
    [8, kick],
    [8, kick],
    [8, kick],
    [4, kick.mask("<1 0 1 0 1 0 1 0>")],
    [8, kick],
    [4, kick.gain(0.24)]
  ),

  arrange(
    [4, silence],
    [8, snare],
    [8, snare],
    [8, snare],
    [4, snare.gain(0.8)],
    [8, snare],
    [4, silence]
  ),

  arrange(
    [4, silence],
    [8, clap.mask("<1 0 1 0 1 0 1 0>")],
    [8, clap],
    [8, clap],
    [4, clap.mask("<0 0 1 0 0 0 1 0>")],
    [8, clap],
    [4, silence]
  ),

  arrange(
    [4, silence],
    [8, hats.gain(0.8)],
    [8, hats],
    [8, hats.gain(1.04)],
    [4, silence],
    [8, stack(hats, hatLift.mask("<1 1 1 0 1 1 1 1>"))],
    [4, hats.gain(0.34)]
  ),

  arrange(
    [4, silence],
    [8, silence],
    [8, perc],
    [8, perc.gain(1.08)],
    [4, fill.mask("<0 0 0 1>")],
    [8, perc.gain(1.12)],
    [4, silence]
  ),

  arrange(
    [4, air],
    [8, silence],
    [8, silence],
    [8, sparkle],
    [4, air.gain(0.7)],
    [8, stack(sparkle, impact.mask("<1 0 0 0 0 0 0 0>"))],
    [4, air.gain(0.5)]
  ),

  arrange(
    [4, silence],
    [8, silence],
    [8, rev.mask("<0 0 0 1>")],
    [8, silence],
    [4, fill.mask("<0 0 0 1>")],
    [8, rev.mask("<0 0 0 1>")],
    [4, silence]
  ),

  arrange(
    [4, silence],
    [8, silence],
    [8, silence],
    [8, silence],
    [4, silence],
    [8, motifTop],
    [4, silence]
  )
)
