// @title Daybreak Ferry
// @genre melodic house / indie dance
// @bpm 120
// @details Original instrumental: breathing chords, a rolling bass pulse and a gradual return. Run `glass-harbor song serve` before pasting.
// @sections intro:4, pulse:8, lift:4, crossing:8, return:16, outro:4
// @section_roles intro:anchor, pulse:groove, lift:lift, crossing:breath, return:return, outro:outro

samples('http://localhost:5432')
setcpm(120 / 4)

const kick = s("kick_main*4").n(1).gain(0.78).orbit(0)
const clap = s("~ clap_main ~ clap_main").n(0).hpf(700).gain(0.38).room(0.12).orbit(1)
const hats = s("hat_closed*8").n("0 1 0 2 0 1 0 3")
  .gain("0.2 0.32 0.14 0.25 0.2 0.33 0.14 0.25").swingBy(0.05, 8).hpf(2500).orbit(1)
const open = s("~ hat_open ~ hat_open").clip(0.65).release(0.03).gain(0.19).hpf(3500).orbit(1)
const perc = s("~ ~ perc_top ~ ~ perc_top ~ ~").n("0 1").speed(0.9)
  .hpf(280).gain(0.1).pan("0.3 0.7").room(0.18).orbit(1)

// The eighth-note pulse follows the same four roots as the chord bed.
const bass = note("<[~ a1 a1 ~ e2 a1 ~ a1 ~ a1 a1 ~ e2 a1 ~ a1] [~ f1 f1 ~ c2 f1 ~ f1 ~ f1 f1 ~ c2 f1 ~ f1] [~ c2 c2 ~ g2 c2 ~ c2 ~ c2 c2 ~ g2 c2 ~ c2] [~ g1 g1 ~ d2 g1 ~ g1 ~ g1 g1 ~ d2 g1 ~ g1]>")
  .slow(2).s("bass_pitched").clip(0.72).release(0.04).lpf(550).gain(0.4).swingBy(0.04, 8).orbit(0)

// Root-labelled single-note samples keep all four voicings in tune.
const chords = note("<[a3,c4,e4,g4] [f3,a3,c4,e4] [c3,g3,c4,e4] [g3,b3,d4,a4]>")
  .slow(2).s("stab_pitched").attack(0.12).release(0.75).hpf(240)
  .lpf(sine.range(850, 1800).slow(16)).gain(0.12)
  .room(0.42).roomsize(4).pan(sine.range(0.35, 0.65).slow(12)).orbit(2)

const arp = note("<[[e4 a4 c5 a4 e4 g4 c5 g4]*2] [[e4 a4 c5 a4 e4 f4 a4 c5]*2] [[e4 g4 c5 g4 e4 g4 b4 g4]*2] [[d4 g4 b4 g4 d4 a4 b4 a4]*2]>")
  .slow(2).s("pluck_pitched").clip(0.75).attack(0.003).release(0.1).hpf(320)
  .lpf(sine.range(1500, 3800).slow(16)).gain("0.17 0.1 0.14 0.09")
  .delay(0.17).delaytime(0.375).delayfeedback(0.28).room(0.22).orbit(3)

// A sparse response gives the return a melody above the repeating arp.
const melody = note("<[e5 ~ ~ d5 ~ c5 ~ ~] [e5 ~ g5 ~ ~ e5 d5 ~] [e5 ~ ~ g5 ~ e5 ~ d5] [d5 ~ ~ b4 ~ d5 ~ ~]>")
  .slow(2).s("pluck_pitched").clip(1).release(0.12).lpf(3000).gain(0.17)
  .delay(0.22).delaytime(0.375).delayfeedback(0.32).room(0.35).orbit(3)

const groove = stack(kick, clap, hats, bass, perc)

arrange(
  [4, stack(chords.lpf(700).gain(0.09), arp.lpf(1100).gain(0.1), hats.gain(0.06))],
  [8, stack(groove, chords, arp)],
  [4, stack(groove, open, chords.lpf(2200), arp.lpf(3200))],
  [8, stack(chords.gain(0.14), arp.lpf(1000).gain(0.1), melody.gain(0.1))],
  [4, stack(groove, chords, arp)],
  [12, stack(groove, open, chords, arp, melody)],
  [4, stack(chords.lpf(650).gain(0.09), arp.lpf(800).gain(0.09))]
).postgain(0.78)
