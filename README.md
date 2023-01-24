https://api.arcade.academy/en/latest/tutorials/card_game/index.html
https://docs.pyscript.net/latest
https://en.wikipedia.org/wiki/ANSI_escape_code

Activate
    printf "\e[?<n>h"

Deactivate
    printf "\e[?<n>l"

n:
- 9 -> X10 mouse reporting, for compatibility with X10's xterm, reports on button press.
- 1000 -> X11 mouse reporting, reports on button press and release.
- 1001 -> highlight reporting, useful for reporting mouse highlights.
- 1002 -> button movement reporting, reports movement when a button is pressed.
- 1003 -> all movement reporting, reports all movements.
- 1005 -> report back encoded as utf-8 (xterm, urxvt, broken in several ways)
- 1006 -> report back as decimal values (xterm, many other terminal emulators, but not urxvt)
- 1015 -> report back as decimal values (urxvt, xterm, other terminal emulators, some applications find it complex to parse)

## Semigraphics
https://en.wikipedia.org/wiki/Semigraphics

### Unicode block elements ([Wikipedia](https://en.wikipedia.org/wiki/Block_Elements))
```
# Upper half
'▀'
# Lower 1/8 -> 7/8
'▁▂▃▄▅▆▇'
# Full block
'█'
# Left 7/8 -> 1/8
'▉▊▋▌▍▎▏'
# Right half
'▐'
# Light, medium, dark shade
'░▒▓'
# Upper 1/8
'▔'
# Right 1/8
'▕'
# Quadrants
'▖▗▘▙▚▛▜▝▞▟'
```