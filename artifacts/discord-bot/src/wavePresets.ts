/**
 * Standalone FFmpeg Video Filter (-vf) Wave Presets.
 * Operating directly on the video's native dimensions to prevent stretching.
 */
export const WAVE_PRESETS = {
    /**
     * Large Wave (formerly Gentle Ripple)
     * A broader, highly visible waving effect across both X and Y axes.
     */
    largeWave: 
        "format=yuv444p,geq='p(X-((sin((T*5*0+(0*15))+(Y/H)*(PI*5.4)))*(-15*2)),Y-((sin((T*5*0+(0*15))+(X/W)*(PI*5.4)))*(-15*2)))',setsar=1:1,format=yuv420p",

    /**
     * Medium Wave (formerly High Frequency Wave)
     * Balanced, distinct wave ripples in both directions.
     */
    mediumWave: 
        "format=yuv444p,geq='p(X-((sin((T*5*0+(0*15))+(Y/H)*(PI*14)))*(-15*2)),Y-((sin((T*5*0+(0*15))+(X/W)*(PI*14)))*(-15*2)))',setsar=1:1,format=yuv420p",

    /**
     * Small Wave (formerly Extreme Shimmer)
     * Fine-grained, tight wave ripples with a lower amplitude.
     */
    smallWave: 
        "format=yuv444p,geq='p(X-((sin((T*5*0+(0*15))+(Y/H)*(PI*20)))*(-15*1.2)),Y-((sin((T*5*0+(0*15))+(X/W)*(PI*20)))*(-15*1.2)))',setsar=1:1,format=yuv420p",

    /**
     * Horizontal Only (formerly Horizontal Drift)
     * Wave distortion applied strictly along the horizontal (X) axis.
     */
    horizontalOnly: 
        "format=yuv444p,geq='p(X-((sin((T*5*0+(0.053*15))+(Y/H)*(PI*10)))*(-15*1.5)),Y-((sin((T*5*0+(0*15))+(X/W)*(PI*0)))*(-15*0)))',setsar=1:1,format=yuv420p",

    /**
     * Vertical Only (formerly Vertical Drift)
     * Wave distortion applied strictly along the vertical (Y) axis.
     */
    verticalOnly: 
        "format=yuv444p,geq='p(X-((sin((T*5*0+(0*15))+(Y/H)*(PI*0)))*(-15*0)),Y-((sin((T*5*0+(0.053*15))+(X/W)*(PI*10)))*(-15*1.6)))',setsar=1:1,format=yuv420p"
} as const;

export type WavePresetKey = keyof typeof WAVE_PRESETS;
