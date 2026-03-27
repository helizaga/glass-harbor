// @title Replace Me
// @genre replace me
// @bpm 124
// @details Pasteable Strudel song file. Run `glass-harbor song serve` before pasting into Strudel web.
// @sections intro:8, groove:16, outro:16

samples('http://localhost:5432')
setcpm(124 / 4)

const kick = s("kick_main*4").gain(1)
const clap = s("~ clap_main ~ clap_main").gain(0.45)
const hats = s("hat_closed*8").gain(0.14)
const air = s("air_texture").slow(8).gain(0.18)

stack(
  arrange(
    [8, silence],
    [16, kick],
    [16, kick]
  ),
  arrange(
    [8, silence],
    [16, clap],
    [16, clap]
  ),
  arrange(
    [8, hats.gain(0.08)],
    [16, hats],
    [16, hats.gain(0.12)]
  ),
  arrange(
    [8, air],
    [16, silence],
    [16, air]
  )
)
