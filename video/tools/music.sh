#!/usr/bin/env bash
# Builds the background track from GarageBand's royalty-free Apple Loops ("Deep Sleep",
# Skyline Heat pack). Needs GarageBand's loop library installed. Output is not committed.
set -euo pipefail
L="/Library/Audio/Apple Loops/Apple/22 Skyline Heat"
OUT="$(dirname "$0")/../public/audio/music.m4a"
LEN=${1:-125}

ffmpeg -v error -y \
  -stream_loop -1 -i "$L/Deep Sleep Synth Pad 01.caf" \
  -stream_loop -1 -i "$L/Deep Sleep Sub Bass 01.caf" \
  -stream_loop -1 -i "$L/Deep Sleep Synth Plucks 01.caf" \
  -stream_loop -1 -i "$L/Deep Sleep Kick 01.caf" \
  -filter_complex "
    [0]atrim=0:$LEN,volume=0.9[pad];
    [1]atrim=0:$((LEN-12)),adelay=12000|12000,volume=0.8[bass];
    [2]atrim=0:$((LEN-24)),adelay=24000|24000,volume=0.55[pluck];
    [3]atrim=0:60,afade=t=in:d=3,afade=t=out:st=56:d=4,adelay=36000|36000,volume=0.5[kick];
    [pad][bass][pluck][kick]amix=inputs=4:normalize=0:duration=first,
    afade=t=in:d=2,afade=t=out:st=$((LEN-6)):d=6,loudnorm=I=-20:TP=-2[out]" \
  -map "[out]" -c:a aac -b:a 192k "$OUT"
echo "wrote $OUT"
