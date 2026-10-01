// @title Pocket Petals
// @genre airy uk garage study / featherlight dance-pop
// @bpm 129
// @details Pasteable song file for Strudel web. Run `glass-harbor song serve` before pasting. Hook-forward, light-footed, PinkPantheress-adjacent study with vocal fragments and a soft garage pulse.
// @sections intro:8, glide:16, hook:8, breakdown:8, return:16, outro:8
// @section_roles intro:anchor, glide:groove, hook:lift, breakdown:breath, return:return, outro:outro

samples('http://localhost:5432')
setcpm(129 / 4)

const kickGlide = s("kick_main*8")
  .n("0 ~ ~ 1 ~ 0 ~ ~")
  .gain("[0.94 0 0 0.82 0 0.92 0 0]")

const kickReturn = s("kick_main*8")
  .n("0 ~ 1 ~ 0 1 ~ ~")
  .gain("[0.98 0 0.72 0 0.96 0.76 0 0]")

const clap = s("~ clap_main ~ clap_main")
  .n("0 1")
  .gain(0.42)
  .room(0.16)

const hatsTight = s("hat_closed*16")
  .n("0 1 0 2 0 1 0 3 0 1 0 2 0 1 0 4")
  .gain("[0.05 0.08 0.05 0.1]*4")
  .pan(sine.range(0.38, 0.62))

const hatsReturn = s("hat_closed*16")
  .n("0 1 0 2 0 3 0 4 0 1 0 2 0 3 0 5")
  .gain("[0.06 0.1 0.06 0.12]*4")
  .pan(sine.range(0.3, 0.7))

const openHat = s("~ hat_open ~ ~ ~ hat_open ~ ~")
  .n("0 1")
  .gain(0.12)
  .delay("0.04:0.125:0.05")

const percSkip = s("perc_top*8")
  .n("0 ~ 1 ~ 0 ~ 1 0")
  .gain("[0.08 0 0.1 0 0.09 0 0.11 0.08]")
  .delay("0.03:0.125:0.06")

const bassGlide = note("<[b1 ~ fs2 ~] [g1 ~ d2 ~] [d2 ~ a1 ~] [a1 ~ e2 ~]>")
  .slow(2)
  .sound("triangle")
  .lpf(420)
  .attack(0.01)
  .decay(0.08)
  .sustain(0.18)
  .release(0.08)
  .gain(0.32)

const bassReturn = note("<[b1 ~ fs2 ~] [g1 ~ d2 ~] [d2 ~ a1 ~] [a1 ~ e2 ~]>")
  .slow(2)
  .sound("triangle,sawtooth")
  .lpf(680)
  .attack(0.01)
  .decay(0.08)
  .sustain(0.22)
  .release(0.08)
  .gain(0.36)

const bassBreak = note("<[b1 ~ ~ ~] [g1 ~ ~ ~] [d2 ~ ~ ~] [a1 ~ ~ ~]>")
  .slow(2)
  .sound("triangle")
  .lpf(260)
  .attack(0.02)
  .decay(0.08)
  .sustain(0.08)
  .release(0.12)
  .gain(0.1)

const padCloud = note("<[b4 d5 fs5 a5] [g4 b4 d5 fs5] [d4 fs4 a4 c5] [a4 c5 e5 g5]>")
  .slow(4)
  .sound("sawtooth")
  .attack(0.16)
  .decay(0.12)
  .sustain(0.4)
  .release(0.3)
  .room(0.42)
  .delay("0.08:0.125:0.08")

const padIntro = padCloud
  .lpf(980)
  .gain(0.06)

const padGlide = padCloud
  .lpf(sine.range(1200, 2400).slow(8))
  .gain(0.08)

const padHook = padCloud
  .lpf(sine.range(1600, 3200).slow(4))
  .gain(0.1)

const hookBell = note("<[fs5 ~ e5 ~ d5 ~ fs5 ~] [d5 ~ b4 ~ d5 ~ fs5 ~] [a4 ~ d5 ~ fs5 ~ e5 ~] [e5 ~ d5 ~ b4 ~ d5 ~]>")
  .slow(2)
  .sound("square,triangle")
  .lpf(1800)
  .attack(0.01)
  .decay(0.08)
  .sustain(0.04)
  .release(0.08)
  .gain(0.08)
  .delay("0.12:0.125:0.1")

const vocalHook = s("vocal_chop*16")
  .n("0 1 0 2 0 1 0 3 0 1 0 2 0 1 0 4")
  .gain("[0.04 0.07 0.05 0.08]*4")
  .pan(sine.range(0.34, 0.66))

const air = s("air_texture")
  .slow(8)
  .gain(0.1)
  .room(0.9)
  .lpf(sine.range(900, 2600).slow(8))

const shimmer = s("shimmer_fx")
  .slow(8)
  .gain(0.05)

const impact = s("impact_wide ~ ~ ~")
  .slow(4)
  .gain(0.2)

stack(
  arrange(
    [8, silence],
    [16, kickGlide],
    [8, kickGlide.gain(0.92)],
    [8, silence],
    [16, kickReturn.gain(1.04)],
    [8, silence]
  ),

  arrange(
    [8, silence],
    [16, clap],
    [8, clap.gain(0.38)],
    [8, silence],
    [16, clap.gain(0.48)],
    [8, silence]
  ),

  arrange(
    [8, hatsTight.gain(0.38)],
    [16, hatsTight],
    [8, hatsTight.gain(0.9)],
    [8, silence],
    [16, hatsReturn.gain(0.96)],
    [8, hatsTight.gain(0.28)]
  ),

  arrange(
    [8, silence],
    [16, silence],
    [8, openHat.gain(0.08)],
    [8, silence],
    [16, openHat.gain(0.14)],
    [8, silence]
  ),

  arrange(
    [8, silence],
    [16, percSkip],
    [8, percSkip.gain(0.9)],
    [8, silence],
    [16, percSkip.gain(1.04)],
    [8, silence]
  ),

  arrange(
    [8, silence],
    [16, bassGlide],
    [8, bassGlide.gain(0.92)],
    [8, bassBreak],
    [16, bassReturn],
    [8, silence]
  ),

  arrange(
    [8, padIntro],
    [16, padGlide],
    [8, padHook],
    [8, padIntro.gain(0.5)],
    [16, padHook.gain(0.94)],
    [8, padIntro.gain(0.72)]
  ),

  arrange(
    [8, silence],
    [16, silence],
    [8, hookBell],
    [8, silence],
    [16, hookBell.gain(1.06)],
    [8, silence]
  ),

  arrange(
    [8, silence],
    [16, vocalHook.gain(0.8)],
    [8, vocalHook.gain(1.06)],
    [8, vocalHook.gain(0.44)],
    [16, vocalHook.gain(1.12)],
    [8, silence]
  ),

  arrange(
    [8, air.gain(1.08)],
    [16, air.gain(0.08)],
    [8, shimmer.gain(0.06)],
    [8, air.gain(0.14)],
    [16, air.gain(0.08)],
    [8, air.gain(0.08)]
  ),

  arrange(
    [8, silence],
    [16, silence],
    [8, silence],
    [8, silence],
    [16, impact.gain(0.8)],
    [8, silence]
  )
)
