#!/bin/bash
# Standalone Freakzinga Test Effect — fixed FFmpeg command
# Usage: ./fzte_standalone.sh <input_video> <output_video> [width] [height]

set -euo pipefail

INPUT="${1:-}"
OUTPUT="${2:-out_fzte.mp4}"
W="${3:-1920}"
H="${4:-1080}"

if [[ -z "$INPUT" ]]; then
    echo "Usage: $0 <input_video> <output_video> [width] [height]"
    exit 1
fi

FONT="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
LUT_URL="https://file.garden/aRsVTo5zvgxNjaSF/a.cube"
DISPLACE_URL="https://file.garden/aTXso15ukD3mnuPI/tv_sim_displacement_map.mov"

# Download LUT once
LUT_FILE="$(mktemp --suffix=.cube)"
trap 'rm -f "$LUT_FILE"' EXIT
curl -sL "$LUT_URL" -o "$LUT_FILE"

# The filter_complex replicates the full fzte pipeline:
#   lut3d → rotate(-45°) → scale → tvsim displacement → wave → rotate(+45°)
#   → hflip → crop/hstack → mirror-right → mirror-bottom → transpose → drawtext → negate

ffmpeg -y \
    -i "$INPUT" \
    -stream_loop -1 -i "$DISPLACE_URL" \
    -filter_complex "
        [0:v]lut3d=${LUT_FILE},format=yuv420p,rotate=-45/180*PI,format=yuv420p,scale=854:854,format=bgr32[00];
        [1:v]format=yuv444p,geq='p(mod(X,W),mod(Y/4,H))',scale=854:854,eq=contrast=0.263334:eval=frame,format=bgr32,hue=b=-0.033[x];
        color=s=854x854:c=#808080,format=bgr32[y];
        [00][x][y]displace=edge=wrap,scale=${W}:${H},setsar=1,format=yuv444p,
        format=yuv444p,scale=640:640,
        geq='p(X-((sin((T*5*0+(0*15))+(Y/H)*(PI*0)))*(-15*0)),Y-((sin((T*5*0+(0.34666*15))+(X/W)*(PI*15)))*(-15*0.8)))',
        scale=${W}:${H},format=yuv420p,rotate=45/180*PI,format=yuv420p,
        hflip,
        crop=${W}*0.840:${H}:${W}*0.840:0,split[right][tmp];
            [tmp]hflip[left];
            [left][right]hstack,
        crop=${W}:${H}:${W}*0.840:0,
        crop=iw/2:ih:0:0,split[left2][tmp2];
            [tmp2]hflip[right2];
            [left2][right2]hstack,
        transpose=3,
        crop=iw/2:ih:0:0,split[left3][tmp3];
            [tmp3]hflip[right3];
            [left3][right3]hstack,
        transpose=1,
        negate,
        drawtext=fontfile=${FONT}:text='%{n}.000':text_align=R:fontcolor=white:fontsize=w/24:box=1:boxcolor=black:boxborderw=7*(text_h):x=(w/2)-(text_w/2):y=(h-text_h)/1.12,
        negate
    " \
    -map 0:a? \
    -c:v libx264 -preset fast -crf 23 -pix_fmt yuv420p \
    -c:a aac -b:a 192k \
    -movflags +faststart \
    "$OUTPUT"

echo "Done: $OUTPUT"
