// @title EDM Pack Preload
// @details Quiet warm-up pass for the custom pack before a serious take.

samples('http://localhost:5432')
setcpm(120 / 4)

stack(
  s("kick_main clap_main hat_closed hat_open perc_top").slow(2).gain(0.03),
  s("impact_wide riser_up shimmer_fx vocal_chop").slow(4).gain(0.025),
  s("air_texture").slow(8).gain(0.02)
)
