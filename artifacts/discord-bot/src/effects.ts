/**
 * effects.ts — Reusable IHTX video/audio effect functions.
 *
 * Each function follows the `ProcessorContext` contract and can be
 * called from any command or pipe-chain handler.  Effects that need
 * FFmpeg are built on `spawnAsync` so they inherit timeout handling,
 * stdout/stderr capture, and non-blocking execution.
 */

import { spawnAsync } from './utils/spawn.js';
import { PROCESS_TIMEOUTS } from './config.js';
import { parseGradientParams, applyGradientmap as applyGradientmapCore } from './commands/gradientmap.js';

// ── Processor context ────────────────────────────────────────────────

export interface ProcessorContext {
  inputFile: string;
  outputFile: string;
  timeout?: number;
}

// ── Video dimension probing ──────────────────────────────────────────

async function getVideoDimensions(
  filePath: string,
): Promise<{ width: number; height: number }> {
  try {
    const result = await spawnAsync('ffprobe', [
      '-v', 'error',
      '-select_streams', 'v:0',
      '-show_entries', 'stream=width,height',
      '-of', 'default=nw=1:nk=1',
      filePath,
    ], { timeout: 10_000 });

    const parts = result.stdout.trim().split(/\s+/).map(Number);
    const width = parts[0] || 1280;
    const height = parts[1] || 720;
    return { width, height };
  } catch {
    console.error('[ffprobe] Failed to resolve dimensions, falling back to 720p');
    return { width: 1280, height: 720 };
  }
}

// ── Random Jitter ────────────────────────────────────────────────────

/**
 * Apply the **Random Jitter** pixel-displacement effect.
 *
 * Uses `geq` with sinusoidal expressions to dynamically compute
 * per-frame pixel matrices.  The formula matches the legacy
 * TypeScript reference exactly:
 *
 *   indexX = i + 67   (i defaults to 1 → 68)
 *   indexY = i + 670  (i defaults to 1 → 671)
 *   divisor = 2.6666666666666665
 *
 *   exprX = ((strength/(25/3))/divisor) * (2*mod(1000*sin(N*indexX),1)-1)
 *   exprY = (strength/divisor)          * (2*mod(1000*sin(N+1000)*indexY,1)-1)
 *
 * Filter chain:
 *   rotate=0 → format=yuv444p → geq → crop → format=yuv420p
 *
 * NOT a standalone command — integrated into the core IHTX processing
 * framework as a reusable function.
 */
export async function applyRandomJitter(
  ctx: ProcessorContext,
  strengthStr: string,
): Promise<void> {
  const strength = parseFloat(strengthStr) || 10;
  const i = 1;
  const indexX = i + 67;
  const indexY = i + 670;

  const { width, height } = await getVideoDimensions(ctx.inputFile);
  const divisor = 2.6666666666666665;

  const exprX = `((${strength}/(25/3))/${divisor})*(2*mod(1000*sin(N*${indexX}),1)-1)`;
  const exprY = `(${strength}/${divisor})*(2*mod(1000*sin(N+1000)*${indexY},1)-1)`;

  const filterChain =
    `rotate=0:iw*1.1:ih*1.1,format=yuv444p,` +
    `geq='p(X+${exprX},Y+${exprY})',` +
    `crop=${width}:${height},format=yuv420p`;

  await spawnAsync('ffmpeg', [
    '-y',
    '-i', ctx.inputFile,
    '-vf', filterChain,
    ctx.outputFile,
  ], { timeout: ctx.timeout || PROCESS_TIMEOUTS.FFMPEG_MS });
}

// ── Real G-Major 4 core filter ───────────────────────────────────────

/**
 * Build the FFmpeg filter-complex string for the Real G-Major 4 effect.
 *
 * Pipeline:
 *   1. Invert all RGB channels  (curves r/g/b = 0/1 1/0)
 *   2. Split into two branches — base (inverted) & overlay (inverted + rubberband +5 st)
 *   3. Overlay pitch-shifted inverted copy on top of inverted base
 *   4. Mix both audio branches (original + pitch-shifted) with doubled volume
 *
 * This is the production TypeScript equivalent of the legacy
 * `_run_realmajor4` from `bot/ihtx_bot.py` and the dual-input
 * `realGMajor4Command` macro from the specification.
 *
 * @param inputPath  Path to the downloaded input video
 * @param outputPath Path to write the output video
 * @param timeout    Optional per-process timeout (ms)
 */
export async function applyRealGMajor4(
  inputPath: string,
  outputPath: string,
  timeout?: number,
): Promise<void> {
  // Pipeline (reference: processAudioVideoMix):
  //   Video  — curves=all=0/0 0.5/1 1/0  (cross-curve solarization)
  //   Audio  — input 0 at pitch=1 (identity) mixed with input 1 at pitch=1.335
  //             (≈ +5 semitones via frequency ratio), then volume×2
  //
  // The same file is fed as both inputs so the pitched copy is derived from
  // the original without a separate pre-process step.
  const fc = [
    // Video: solarization cross-curve on all channels
    `[0:v]curves=all='0/0 0.5/1 1/0'[vout]`,
    // Audio branch 0: identity (pitch=1)
    `[0:a]rubberband=pitch=1[aud0]`,
    // Audio branch 1: pitch shifted up by ×1.335 (≈ +5 st), quality mode
    `[1:a]rubberband=pitch=1.335:window=long:pitchq=quality[aud1]`,
    // Mix both branches and double volume
    `[aud0][aud1]amix=inputs=2:duration=longest[mixed]`,
    `[mixed]volume=2[aout]`,
  ].join(';');

  await spawnAsync('ffmpeg', [
    '-y',
    '-i', inputPath,
    '-i', inputPath,   // second input — source for the pitched audio layer
    '-filter_complex', fc,
    '-map', '[vout]',
    '-map', '[aout]',
    '-c:v', 'libx264',
    '-preset', 'fast',
    '-crf', '23',
    '-pix_fmt', 'yuv420p',
    '-c:a', 'pcm_s16le',
    outputPath,
  ], { timeout: timeout || PROCESS_TIMEOUTS.REALGM4_MS });
}

// ── Ripple ──────────────────────────────────────────────────────────────

/**
 * Apply the **Ripple** radial displacement distortion.
 *
 * Uses `geq` with sinusoidal ripple around the video center:
 *
 *   r = hypot(X-W/2, Y-H/2)
 *   disp = r + amp * sin(2*PI*spd*T - phase - r/freq)
 *   angle = atan2(Y-H/2, X-W/2)
 *   source X = W/2 + disp * cos(angle)
 *   source Y = H/2 + disp * sin(angle)
 *
 * @param ctx  Processor context (input/output files, optional timeout)
 * @param speed      Animation speed (default 1.0)
 * @param frequency  Ripple frequency (default 30.0)
 * @param amplitude  Displacement amplitude in pixels (default 10.0)
 * @param phase      Initial phase offset (default 0.0)
 */
export async function applyRipple(
  ctx: ProcessorContext,
  speed = 1.0,
  frequency = 30.0,
  amplitude = 10.0,
  phase = 0.0,
): Promise<void> {
  const rExpr = 'hypot(X-W*0.5,Y-H*0.5)';
  const disp = `(${rExpr}+${amplitude}*sin(2*PI*${speed}*T-(${phase})+(-(${rExpr})/${frequency})))`;
  const angle = 'atan2(Y-H*0.5,X-W*0.5)';

  const filterChain =
    `format=yuv444p,` +
    `geq='p(W*0.5+${disp}*cos(${angle}),H*0.5+${disp}*sin(${angle}))',` +
    `scale=iw:ih,format=yuv420p`;

  await spawnAsync('ffmpeg', [
    '-y', '-i', ctx.inputFile,
    '-vf', filterChain,
    '-c:a', 'copy',
    ctx.outputFile,
  ], { timeout: ctx.timeout || PROCESS_TIMEOUTS.FFMPEG_MS });
}

// ── Pan ─────────────────────────────────────────────────────────────────

/**
 * Apply the **Pan** pixel offset effect.
 *
 * Shifts the entire frame by (px, py) pixels with boundary clipping.
 *
 * @param ctx  Processor context
 * @param px   Horizontal pixel offset (default 0)
 * @param py   Vertical pixel offset (default 0)
 */
export async function applyPan(
  ctx: ProcessorContext,
  px = 0.0,
  py = 0.0,
): Promise<void> {
  const filterChain =
    `format=yuv444p,` +
    `geq='p(clip(X+${px},0,W-1),clip(Y+${py},0,H-1))` +
    `:cb(clip(X+${px},0,W-1),clip(Y+${py},0,H-1))` +
    `:cr(clip(X+${px},0,W-1),clip(Y+${py},0,H-1))',` +
    `scale=iw:ih,format=yuv420p`;

  await spawnAsync('ffmpeg', [
    '-y', '-i', ctx.inputFile,
    '-vf', filterChain,
    '-c:a', 'copy',
    ctx.outputFile,
  ], { timeout: ctx.timeout || PROCESS_TIMEOUTS.FFMPEG_MS });
}

// ── Tile ────────────────────────────────────────────────────────────────

/**
 * Apply the **Tile** repetitive tiling effect.
 *
 * Repeats the frame tx×ty times using geq mod expressions:
 *   source X = mod(X * tx, W)
 *   source Y = mod(Y * ty, H)
 *
 * @param ctx  Processor context
 * @param tx   Horizontal tile count (default 2)
 * @param ty   Vertical tile count (default 2)
 */
export async function applyTile(
  ctx: ProcessorContext,
  tx = 2.0,
  ty = 2.0,
): Promise<void> {
  const filterChain =
    `format=yuv444p,` +
    `geq='p(mod(X*${tx},W),mod(Y*${ty},H))` +
    `:cb(mod(X*${tx},W),mod(Y*${ty},H))` +
    `:cr(mod(X*${tx},W),mod(Y*${ty},H))',` +
    `scale=iw:ih,format=yuv420p`;

  await spawnAsync('ffmpeg', [
    '-y', '-i', ctx.inputFile,
    '-vf', filterChain,
    '-c:a', 'copy',
    ctx.outputFile,
  ], { timeout: ctx.timeout || PROCESS_TIMEOUTS.FFMPEG_MS });
}

// ── Zoom (updated: scale+crop) ──────────────────────────────────────────

/**
 * Apply the **Zoom** effect using scale+crop approach.
 *
 * Scales the video up by `amt`, then center-crops back to original size.
 * This produces a clean zoom without the artifacts of the old geq approach.
 *
 * @param ctx  Processor context
 * @param amt  Zoom multiplier (default 2.0, must be > 0.1)
 */
export async function applyZoom(
  ctx: ProcessorContext,
  amt = 2.0,
): Promise<void> {
  const s = Math.max(0.1, amt);
  const filterChain =
    `scale=iw*${s}:ih*${s},` +
    `crop=iw/${s}:ih/${s}:(iw-iw/${s})/2:(ih-ih/${s})/2`;

  await spawnAsync('ffmpeg', [
    '-y', '-i', ctx.inputFile,
    '-vf', filterChain,
    '-c:a', 'copy',
    ctx.outputFile,
  ], { timeout: ctx.timeout || PROCESS_TIMEOUTS.FFMPEG_MS });
}

// ── Scroll (multi-mode) ─────────────────────────────────────────────────

/**
 * Apply the **Scroll** effect in one of three modes:
 *
 * 1. Named params: scroll=hpos=0.5 or scroll=hpos=0.5;ypos=0.3
 *    → Uses FFmpeg's native scroll filter
 * 2. Continuous: scroll=h;v (0.0–1.0 per axis)
 *    → Uses FFmpeg's native scroll filter
 * 3. Animated pan: scroll=x1:y1:x2:y2[:dur] (4+ numeric params)
 *    → Uses geq with time-dependent expressions
 *
 * @param ctx    Processor context
 * @param params Raw params array from the effect string
 */
export async function applyScroll(
  ctx: ProcessorContext,
  params: string[],
): Promise<void> {
  const hasNamed = params.some(
    p => p.startsWith('hpos') || p.startsWith('vpos') || p.startsWith('ypos'),
  );
  const allNumeric = params.every(p => {
    const v = p.includes('=') ? p.split('=')[1] : p;
    return !isNaN(Number(v));
  });

  if (hasNamed) {
    // Mode 1: Named params → native scroll filter
    const parts: string[] = [];
    for (const p of params) {
      if (!p.includes('=')) continue;
      const [k, v] = p.split('=');
      const key = k.trim().toLowerCase();
      const val = v.trim();
      if (key === 'hpos') parts.push(`hpos=${val}`);
      else if (key === 'vpos' || key === 'ypos') parts.push(`vpos=${val}`);
    }
    const vfScroll = parts.length ? parts.join(',') : 'hpos=0.5';
    await spawnAsync('ffmpeg', [
      '-y', '-i', ctx.inputFile,
      '-vf', `scroll=${vfScroll}`,
      '-c:a', 'copy',
      ctx.outputFile,
    ], { timeout: ctx.timeout || PROCESS_TIMEOUTS.FFMPEG_MS });
  } else if (params.length >= 4 && allNumeric) {
    // Mode 3: Animated pan via geq
    const nums = params.map(Number);
    const x1 = nums[0] ?? 0;
    const y1 = nums[1] ?? 0;
    const x2 = nums[2] ?? 0;
    const y2 = nums[3] ?? 0;
    const dur = nums[4] ?? 0;
    const tExpr = dur > 0 ? `T/${dur}` : 'T';
    const panX = `${x1}+(${x2}-${x1})*${tExpr}`;
    const panY = `${y1}+(${y2}-${y1})*${tExpr}`;
    const filterChain =
      `format=yuv444p,` +
      `geq='p(clip(X+${panX},0,W-1),clip(Y+${panY},0,H-1))` +
      `:cb(clip(X+${panX},0,W-1),clip(Y+${panY},0,H-1))` +
      `:cr(clip(X+${panX},0,W-1),clip(Y+${panY},0,H-1))',` +
      `scale=iw:ih,format=yuv420p`;
    await spawnAsync('ffmpeg', [
      '-y', '-i', ctx.inputFile,
      '-vf', filterChain,
      '-c:a', 'copy',
      ctx.outputFile,
    ], { timeout: ctx.timeout || PROCESS_TIMEOUTS.FFMPEG_MS });
  } else {
    // Mode 2: Continuous scroll → native scroll filter
    const hSpeed = Number(params[0]) || 0;
    const vSpeed = Number(params[1]) || 0;
    const parts: string[] = [];
    if (hSpeed !== 0) parts.push(`hpos=${hSpeed}`);
    if (vSpeed !== 0) parts.push(`vpos=${vSpeed}`);
    const vfScroll = parts.length ? parts.join(',') : 'hpos=0.5';
    await spawnAsync('ffmpeg', [
      '-y', '-i', ctx.inputFile,
      '-vf', `scroll=${vfScroll}`,
      '-c:a', 'copy',
      ctx.outputFile,
    ], { timeout: ctx.timeout || PROCESS_TIMEOUTS.FFMPEG_MS });
  }
}

// ── Mirror (updated: parametric fold + presets) ──────────────────────────

/**
 * Apply the **Mirror** effect.
 *
 * Two modes:
 * 1. Preset: mirror=left|right|top|bottom (or l/r/t/b)
 *    → Uses split/crop/hflip/hstack or split/crop/vflip/vstack
 * 2. Parametric fold: mirror=angle[,cx,cy]
 *    → Folds the image along a line through (cx,cy) at `angle` degrees
 *    using rotate + geq + counter-rotate + crop
 *
 * @param ctx    Processor context
 * @param params Raw params array
 */
export async function applyMirror(
  ctx: ProcessorContext,
  params: string[],
): Promise<void> {
  const first = (params[0] ?? '').toLowerCase().trim();
  const aliases: Record<string, string> = { l: 'left', r: 'right', t: 'top', b: 'bottom' };
  const resolved = aliases[first] ?? first;
  const presets = new Set(['left', 'right', 'top', 'bottom']);

  let filterChain: string;

  if (presets.has(resolved)) {
    // Preset mode
    const presetVf: Record<string, string> = {
      left:   "split[_ma][_mb];[_ma]crop=iw/2:ih:0:0[_mL];[_mb]crop=iw/2:ih:0:0,hflip[_mR];[_mL][_mR]hstack",
      right:  "split[_ma][_mb];[_ma]crop=iw/2:ih:iw/2:0,hflip[_mL];[_mb]crop=iw/2:ih:iw/2:0[_mR];[_mL][_mR]hstack",
      top:    "split[_ma][_mb];[_ma]crop=iw:ih/2:0:0[_mT];[_mb]crop=iw:ih/2:0:0,vflip[_mB];[_mT][_mB]vstack",
      bottom: "split[_ma][_mb];[_ma]crop=iw:ih/2:0:ih/2,vflip[_mT];[_mb]crop=iw:ih/2:0:ih/2[_mB];[_mT][_mB]vstack",
    };
    filterChain = presetVf[resolved] ?? presetVf['left']!;
  } else {
    // Parametric fold mode: mirror=angle[,cx,cy]
    const A = first ? parseFloat(first) : 90.0;
    const cx = params.length > 1 ? parseFloat(params[1]) : 0.5;
    const cy = params.length > 2 ? parseFloat(params[2]) : 0.5;
    const aRad = `${A}/180*PI`;
    const cxOff = cx - 0.5;
    const cyOff = cy - 0.5;
    const cxTerm = cxOff >= 0
      ? `+${cxOff.toFixed(6)}*(W/2)*sin(${aRad})`
      : `${cxOff.toFixed(6)}*(W/2)*sin(${aRad})`;
    const cyTerm = cyOff >= 0
      ? `+${cyOff.toFixed(6)}*(H/2)*cos(${aRad})`
      : `${cyOff.toFixed(6)}*(H/2)*cos(${aRad})`;
    const foldY = `H/2${cxTerm}${cyTerm}`;
    filterChain =
      `rotate=${A}/180*PI:iw*2:ih*2,` +
      `geq='if(gte(Y,${foldY}),p(X,2*(${foldY})-Y),p(X,Y))',` +
      `format=yuv420p,` +
      `rotate=${A}/-180*PI,` +
      `crop=iw/2:ih/2,` +
      `format=yuv420p`;
  }

  await spawnAsync('ffmpeg', [
    '-y', '-i', ctx.inputFile,
    '-vf', filterChain,
    '-c:a', 'copy',
    ctx.outputFile,
  ], { timeout: ctx.timeout || PROCESS_TIMEOUTS.FFMPEG_MS });
}

// ── Left Split ───────────────────────────────────────────────────────────

/**
 * Apply the **LeftSplit** effect.
 *
 * Splits the video in half, applies inner effects to the left half,
 * then hflips and hstacks with the right half.
 *
 * This is a multi-step process:
 * 1. Crop left half → apply inner effects via recursive pipeline
 * 2. Crop right half (no effects)
 * 3. hflip the affected left half
 * 4. hstack left(hflipped) + right
 * 5. Mux audio from original
 *
 * @param ctx          Processor context
 * @param innerEffects Inner pipe effects to apply to the left half
 * @param applyEffects Function that applies a set of effects to an input/output pair
 */
export async function applyLeftSplit(
  ctx: ProcessorContext,
  innerEffects: (inputPath: string, outputPath: string) => Promise<void>,
): Promise<void> {
  const { width, height } = await getVideoDimensions(ctx.inputFile);
  const halfW = Math.floor(width / 2);

  // Step 1: Extract and process left half
  const leftRaw = ctx.outputFile + '.left_raw.mp4';
  const leftFx = ctx.outputFile + '.left_fx.mp4';
  const rightRaw = ctx.outputFile + '.right_raw.mp4';

  await spawnAsync('ffmpeg', [
    '-y', '-i', ctx.inputFile,
    '-vf', `crop=${halfW}:${height}:0:0`,
    '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
    '-pix_fmt', 'yuv420p', '-c:a', 'copy',
    leftRaw,
  ], { timeout: ctx.timeout || PROCESS_TIMEOUTS.FFMPEG_MS });

  // Apply inner effects to left half
  await innerEffects(leftRaw, leftFx);

  // Step 2: Extract right half (no effects)
  await spawnAsync('ffmpeg', [
    '-y', '-i', ctx.inputFile,
    '-vf', `crop=${halfW}:${height}:${halfW}:0`,
    '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
    '-pix_fmt', 'yuv420p', '-c:a', 'copy',
    rightRaw,
  ], { timeout: ctx.timeout || PROCESS_TIMEOUTS.FFMPEG_MS });

  // Step 3: hflip left + hstack
  await spawnAsync('ffmpeg', [
    '-y',
    '-i', leftFx,
    '-i', rightRaw,
    '-filter_complex',
    `[0:v]hflip[lflipped];[lflipped][1:v]hstack=inputs=2[vout]`,
    '-map', '[vout]',
    '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
    '-pix_fmt', 'yuv420p',
    '-an',
    ctx.outputFile,
  ], { timeout: ctx.timeout || PROCESS_TIMEOUTS.FFMPEG_MS });
}

// ── Right Split ──────────────────────────────────────────────────────────

/**
 * Apply the **RightSplit** effect.
 *
 * Splits the video in half, applies inner effects to the right half,
 * then hstacks left + affected right.
 *
 * This is a multi-step process:
 * 1. Crop left half (no effects)
 * 2. Crop right half → apply inner effects via recursive pipeline
 * 3. hstack left + right(affected)
 * 4. Mux audio from original
 *
 * @param ctx          Processor context
 * @param innerEffects Inner pipe effects to apply to the right half
 * @param applyEffects Function that applies a set of effects to an input/output pair
 */
export async function applyRightSplit(
  ctx: ProcessorContext,
  innerEffects: (inputPath: string, outputPath: string) => Promise<void>,
): Promise<void> {
  const { width, height } = await getVideoDimensions(ctx.inputFile);
  const halfW = Math.floor(width / 2);

  const leftRaw = ctx.outputFile + '.left_raw.mp4';
  const rightRaw = ctx.outputFile + '.right_raw.mp4';
  const rightFx = ctx.outputFile + '.right_fx.mp4';

  // Step 1: Extract left half (no effects)
  await spawnAsync('ffmpeg', [
    '-y', '-i', ctx.inputFile,
    '-vf', `crop=${halfW}:${height}:0:0`,
    '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
    '-pix_fmt', 'yuv420p', '-c:a', 'copy',
    leftRaw,
  ], { timeout: ctx.timeout || PROCESS_TIMEOUTS.FFMPEG_MS });

  // Step 2: Extract and process right half
  await spawnAsync('ffmpeg', [
    '-y', '-i', ctx.inputFile,
    '-vf', `crop=${halfW}:${height}:${halfW}:0`,
    '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
    '-pix_fmt', 'yuv420p', '-c:a', 'copy',
    rightRaw,
  ], { timeout: ctx.timeout || PROCESS_TIMEOUTS.FFMPEG_MS });

  // Apply inner effects to right half
  await innerEffects(rightRaw, rightFx);

  // Step 3: hstack left + right(affected)
  await spawnAsync('ffmpeg', [
    '-y',
    '-i', leftRaw,
    '-i', rightFx,
    '-filter_complex',
    `[0:v][1:v]hstack=inputs=2[vout]`,
    '-map', '[vout]',
    '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
    '-pix_fmt', 'yuv420p',
    '-an',
    ctx.outputFile,
  ], { timeout: ctx.timeout || PROCESS_TIMEOUTS.FFMPEG_MS });
}

// ── Nepeta overlay ──────────────────────────────────────────────────────
// Overlays the Nepeta cat-ear PNG (or custom URL) scaled to video dimensions.
// The PNG loops for the entire video duration; -shortest ensures the output
// ends when the video track ends (fixes the "video goes short" case).

const NEPETA_DEFAULT_URL = 'https://files.catbox.moe/i4d60t.png';

export async function applyNepeta(
  ctx: ProcessorContext,
  imageUrl?: string,
): Promise<void> {
  const url = imageUrl || NEPETA_DEFAULT_URL;

  // Download the overlay image to a temp file
  const https = await import('node:https');
  const fs = await import('node:fs');
  const os = await import('node:os');
  const path = await import('node:path');
  const tmpDir = os.tmpdir();
  const imgPath = path.join(tmpDir, `nepeta_${Date.now()}.png`);

  await new Promise<void>((resolve, reject) => {
    const file = fs.createWriteStream(imgPath);
    https.get(url, { headers: { 'User-Agent': 'Mozilla/5.0 (compatible; IHTX-Bot)' } }, (res) => {
      if (res.statusCode && res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        // Follow redirect
        https.get(res.headers.location, { headers: { 'User-Agent': 'Mozilla/5.0 (compatible; IHTX-Bot)' } }, (res2) => {
          res2.pipe(file);
          file.on('finish', () => { file.close(); resolve(); });
        }).on('error', reject);
      } else {
        res.pipe(file);
        file.on('finish', () => { file.close(); resolve(); });
      }
    }).on('error', reject);
  });

  // Build filter_complex: loop the PNG, scale2ref to video dims, overlay at (0,0)
  const fc = [
    '[1:v]format=rgba,loop=loop=-1:size=1[_nepeta];',
    '[_nepeta][0:v]scale2ref=w=ref_w:h=ref_h:flags=lanczos[_nimg][_vid];',
    '[_vid][_nimg]overlay=0:0:eof_action=repeat[vout]',
  ].join('');

  await spawnAsync('ffmpeg', [
    '-loglevel', 'error', '-hide_banner', '-y',
    '-i', ctx.inputFile,
    '-i', imgPath,
    '-filter_complex', fc,
    '-map', '[vout]',
    '-map', '0:a?',
    '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
    '-pix_fmt', 'yuv420p',
    '-c:a', 'copy',
    '-shortest',
    ctx.outputFile,
  ], { timeout: ctx.timeout || PROCESS_TIMEOUTS.FFMPEG_MS });

  // Cleanup temp image
  try { fs.unlinkSync(imgPath); } catch {}
}

// ── Gradient map ────────────────────────────────────────────────────────
// Pipe-effect wrapper around the gradientmap command. Parses the same
// color-stop syntax (R,G,B[,A,pos] ...) and runs FFmpeg via the filter
// built by commands/gradientmap.ts.

export async function applyGradientmap(
  ctx: ProcessorContext,
  params: string,
): Promise<void> {
  const tokens: string[] = [];
  let cur = '';
  let depth = 0;
  for (const ch of params.trim()) {
    if (ch === '[') { depth++; cur += ch; }
    else if (ch === ']') { depth--; cur += ch; }
    else if ((ch === ' ' || ch === '\t') && depth === 0) {
      if (cur) { tokens.push(cur); cur = ''; }
    } else if ((ch === ';' || ch === '|') && depth === 0) {
      if (cur) { tokens.push(cur); cur = ''; }
    } else {
      cur += ch;
    }
  }
  if (cur) tokens.push(cur);

  const cleaned = tokens.map((t) => t.trim()).filter(Boolean);
  if (!cleaned.length) {
    throw new Error('gradientmap: no color stops provided');
  }

  const parsed = parseGradientParams(cleaned);
  if (!parsed.ok) {
    throw new Error(parsed.error);
  }

  const result = await applyGradientmapCore(
    ctx.inputFile,
    ctx.outputFile,
    parsed.stops,
    ctx.timeout,
  );
  if (!result.ok) {
    throw new Error(result.error || 'gradientmap: ffmpeg failed');
  }
}

// ── Wave ───────────────────────────────────────────────────────────────

/**
 * Apply the **Wave** sinusoidal pixel-displacement distortion.
 *
 * Parameters are passed as a pipe-style token array:
 *   hSpeed|hFreq|hAmp|hPhase|vSpeed|vFreq|vAmp|vPhase|separateWaves|noPixelClipping
 *
 * Defaults:
 *   h/v speed = 0, h/v frequency = 0, h/v amplitude = 0, h/v phase = 0,
 *   separateWaves = false, noPixelClipping = false.
 */
export async function applyWave(
  ctx: ProcessorContext,
  params: string[] = [],
): Promise<void> {
  const parseBool = (val: string | undefined): boolean => {
    if (!val) return false;
    const s = String(val).toLowerCase().trim();
    return ['1', 'true', 't', 'y', 'yes', '+', 'on', 'sep', 'noclip'].includes(s);
  };
  const parseNum = (val: string | undefined, def: number): number => {
    const n = parseFloat(val || '');
    return Number.isNaN(n) ? def : n;
  };

  const hSpeed = parseNum(params[0], 0);
  const hFreq = parseNum(params[1], 0);
  const hAmp = parseNum(params[2], 0);
  const hPhase = parseNum(params[3], 0);
  const vSpeed = parseNum(params[4], 0);
  const vFreq = parseNum(params[5], 0);
  const vAmp = parseNum(params[6], 0);
  const vPhase = parseNum(params[7], 0);
  const separateWaves = parseBool(params[8]);
  const noPixelClipping = parseBool(params[9]);

  // Displacement is scaled by W/640 so the visual amplitude is proportional to
  // the input's native width — matching the old "scale-to-640, apply wave, scale-back"
  // behaviour without needing a dimension probe or explicit scale steps.
  const eqX = `X-((sin((T*5*${vSpeed}+(${vPhase}*15))+(Y/H)*(PI*${vFreq})))*(-15*${vAmp}*(W/640)))`;
  const eqY = `Y-((sin((T*5*${hSpeed}+(${hPhase}*15))+(X/W)*(PI*${hFreq})))*(-15*${hAmp}*(W/640)))`;

  let filterChain = '';
  if (noPixelClipping) {
    filterChain += 'drawbox=t=1,';
  }
  filterChain += 'format=yuv444p,';

  if (separateWaves) {
    filterChain += `geq='p(${eqX},Y)',geq='p(X,${eqY})',`;
  } else {
    filterChain += `geq='p(${eqX},${eqY})',`;
  }

  filterChain += 'setsar=1:1,format=yuv420p';

  await spawnAsync('ffmpeg', [
    '-y', '-i', ctx.inputFile,
    '-vf', filterChain,
    '-c:a', 'copy',
    ctx.outputFile,
  ], { timeout: ctx.timeout || PROCESS_TIMEOUTS.FFMPEG_MS });
}
