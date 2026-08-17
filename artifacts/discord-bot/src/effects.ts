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
import { WAVE_PRESETS, WavePresetKey } from './wavePresets.js';
import { buildVocoderCommand } from './commands/scgv.js';
import { makeTempDir, cleanupDir, downloadUrl } from './utils/temp.js';
import path from 'node:path';

// ── Processor context ────────────────────────────────────────────────

export interface ProcessorContext {
  inputFile: string;
  outputFile: string;
  timeout?: number;
}

/**
 * Apply user-supplied FFmpeg arguments between the input and output paths.
 * The tokenizer deliberately keeps quoted geq/filter_complex expressions
 * together, including commas, brackets, parentheses, and nested math.
 */
export async function applyRawFfmpeg(
  ctx: ProcessorContext,
  rawArgs: string,
): Promise<void> {
  const args: string[] = [];
  let token = '';
  let quote = '';
  let escaped = false;
  for (const ch of rawArgs.trim()) {
    if (escaped) { token += ch; escaped = false; continue; }
    if (ch === '\\' && quote === '"') { escaped = true; continue; }
    if (quote) {
      if (ch === quote) quote = '';
      else token += ch;
    } else if (ch === "'" || ch === '"') {
      quote = ch;
    } else if (/\s/.test(ch)) {
      if (token) { args.push(token); token = ''; }
    } else {
      token += ch;
    }
  }
  if (escaped) token += '\\';
  if (quote) throw new Error('ffmpeg arguments contain an unterminated quote');
  if (token) args.push(token);
  if (!args.length) throw new Error('ffmpeg pipe effect requires arguments');

  const probe = async (entries: string[]): Promise<string> => {
    const result = await spawnAsync('ffprobe', entries, { timeout: 10_000 });
    return result.stdout.trim();
  };
  const [durationRaw, frameRateRaw, frameCountRaw, widthRaw, heightRaw, sampleRateRaw] =
    await Promise.all([
      probe(['-v', 'error', '-show_entries', 'format=duration', '-of', 'default=nw=1:nk=1', ctx.inputFile]),
      probe(['-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=r_frame_rate', '-of', 'default=nw=1:nk=1', ctx.inputFile]),
      probe(['-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=nb_frames', '-of', 'default=nw=1:nk=1', ctx.inputFile]),
      probe(['-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width', '-of', 'default=nw=1:nk=1', ctx.inputFile]),
      probe(['-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=height', '-of', 'default=nw=1:nk=1', ctx.inputFile]),
      probe(['-v', 'error', '-select_streams', 'a:0', '-show_entries', 'stream=sample_rate', '-of', 'default=nw=1:nk=1', ctx.inputFile]),
    ]);
  const duration = Number(durationRaw) || 0;
  const fpsParts = frameRateRaw.split('/');
  const fps = fpsParts.length === 2 ? Number(fpsParts[0]) / Number(fpsParts[1]) : Number(frameRateRaw);
  const vars: Record<string, string> = {
    '$vd': String(duration), '$d': String(duration),
    '$fr': String(fps || 0), '$f': String(fps || 0),
    '$fc': frameCountRaw || '0', '$w': widthRaw || '0',
    '$h': heightRaw || '0', '$sr': sampleRateRaw || '0',
    '$T': duration > 0 ? `(t/${duration})` : 't',
  };
  let expanded = rawArgs;
  for (const [key, value] of Object.entries(vars)) {
    expanded = key === '$T'
      ? expanded.replace(/\$T(?![A-Za-z0-9_])/g, value)
      : expanded.split(key).join(value);
  }
  // Match the Python pipe engine's convenience function for expression math.
  expanded = expanded.replace(
    /lerp\(([^(),]+),([^(),]+),([^()]+)\)/g,
    '(($1)+(($2)-($1))*($3))',
  );
  // Re-tokenize after substitutions so quoted filter arguments remain intact.
  const finalArgs = shellLikeSplit(expanded);
  const result = await spawnAsync('ffmpeg', [
    '-loglevel', 'error', '-hide_banner', '-y', '-i', ctx.inputFile,
    ...finalArgs, ctx.outputFile,
  ], { timeout: ctx.timeout || PROCESS_TIMEOUTS.FFMPEG_MS });
  if (result.code !== 0) throw new Error(result.stderr.slice(-1200) || 'FFmpeg failed');
}

function shellLikeSplit(value: string): string[] {
  const result: string[] = [];
  let current = '';
  let quote = '';
  for (const ch of value) {
    if (quote) {
      if (ch === quote) quote = '';
      else current += ch;
    } else if (ch === "'" || ch === '"') quote = ch;
    else if (/\s/.test(ch)) {
      if (current) { result.push(current); current = ''; }
    } else current += ch;
  }
  if (quote) throw new Error('ffmpeg arguments contain an unterminated quote');
  if (current) result.push(current);
  return result;
}

// ── Pitch transition ───────────────────────────────────────────────────

/**
 * Sweep one or more voices linearly between semitone values.
 *
 * Params use the uploaded pitch CLI syntax:
 *   pitchtransition=-5,9;5,-9
 */
export async function applyPitchTransition(
  ctx: ProcessorContext,
  params: string[],
): Promise<void> {
  const raw = params.join(' ').trim().replace(/^--pitch(?:=|\s*)/i, '');
  // Custom export parsing can normalize semicolons to spaces, so accept both
  // `-7,7;7,-7` and the equivalent `-7,7 7,-7`.
  const number = '[+-]?(?:\\d+(?:\\.\\d*)?|\\.\\d+)(?:[eE][+-]?\\d+)?';
  const pairRe = new RegExp(`(${number})\\s*,\\s*(${number})`, 'g');
  const matches = [...raw.matchAll(pairRe)];
  const compactRaw = raw.replace(/[\s;]+/g, '');
  const compactMatches = matches
    .map((match) => `${match[1]},${match[2]}`)
    .join('');
  if (!matches.length || compactMatches !== compactRaw) {
    throw new Error(`pitchtransition: invalid voice \`${raw}\`; expected start,end;start,end`);
  }
  const voices = matches.map((match) => ({
    start: Number(match[1]),
    end: Number(match[2]),
  }));

  if (!voices.length) throw new Error('pitchtransition requires start,end[;start,end;...]');
  if (voices.length > 100) throw new Error('pitchtransition supports at most 100 voices');

  const durationResult = await spawnAsync('ffprobe', [
    '-v', 'error', '-show_entries', 'format=duration',
    '-of', 'default=noprint_wrappers=1:nokey=1', ctx.inputFile,
  ], { timeout: 15_000 });
  const duration = Number(durationResult.stdout.trim());
  if (!Number.isFinite(duration) || duration <= 0) {
    throw new Error('pitchtransition could not determine input duration');
  }

  const fs = await import('node:fs');
  const os = await import('node:os');
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'pitchtransition-'));
  const transitionLatency = 0.08;
  try {
    const voiceFiles: string[] = [];
    for (let index = 0; index < voices.length; index += 1) {
      const voice = voices[index]!;
      const lines: string[] = [];
      for (let step = 0; step <= Math.floor((duration + transitionLatency) / 0.01); step += 1) {
        const time = Math.min(step * 0.01, duration + transitionLatency);
        const progress = Math.min(time, duration) / duration;
        const pitch = voice.start + (voice.end - voice.start) * progress;
        lines.push(`${Math.round(time * 48000)} ${pitch.toFixed(10)}`);
      }
      const commandFile = path.join(tmpDir, `transition_${index}.txt`);
      fs.writeFileSync(commandFile, `${lines.join('\n')}\n`);
      const paddedFile = path.join(tmpDir, `padded_${index}.wav`);
      const padded = await spawnAsync('ffmpeg', [
        '-y', '-i', ctx.inputFile, '-vn', '-af',
        `apad=pad_dur=${transitionLatency.toFixed(6)},atrim=duration=${(duration + transitionLatency).toFixed(6)}`,
        '-c:a', 'pcm_s16le', paddedFile,
      ], { timeout: ctx.timeout || PROCESS_TIMEOUTS.FFMPEG_MS });
      if (padded.code !== 0) throw new Error(`pitchtransition padding failed: ${padded.stderr.slice(-500)}`);
      const voiceFile = path.join(tmpDir, `voice_${index}.wav`);
      const rendered = await spawnAsync('rubberband-r3', [
        '-3', '--pitchmap', commandFile, '-t', '1', paddedFile, voiceFile,
      ], { timeout: ctx.timeout || PROCESS_TIMEOUTS.FFMPEG_MS });
      if (rendered.code !== 0) throw new Error(`pitchtransition voice ${index + 1} failed: ${rendered.stderr.slice(-500)}`);
      voiceFiles.push(voiceFile);
    }

    let mixed: string;
    if (voiceFiles.length === 1) {
      // Match the reference CLI: a solo transition bypasses the mixer.
      mixed = voiceFiles[0]!;
    } else {
      mixed = path.join(tmpDir, 'mixed.wav');
      const mixArgs = ['-y', ...voiceFiles.flatMap((file) => ['-i', file]),
        '-filter_complex',
        `amix=inputs=${voiceFiles.length}:duration=longest:dropout_transition=0:normalize=1`,
        '-c:a', 'pcm_s16le', mixed];
      const mixedResult = await spawnAsync('ffmpeg', mixArgs, {
        timeout: ctx.timeout || PROCESS_TIMEOUTS.FFMPEG_MS,
      });
      if (mixedResult.code !== 0) throw new Error(`pitchtransition mix failed: ${mixedResult.stderr.slice(-500)}`);
    }

    const hasVideo = await spawnAsync('ffprobe', [
      '-v', 'error', '-select_streams', 'v:0',
      '-show_entries', 'stream=codec_type', '-of', 'default=nw=1:nk=1', ctx.inputFile,
    ], { timeout: 15_000 });
    const video = hasVideo.stdout.trim() === 'video';
    const remuxArgs = video
      ? ['-y', '-i', ctx.inputFile, '-i', mixed, '-map', '0:v:0', '-map', '1:a:0',
        '-map_metadata', '-1', '-avoid_negative_ts', 'make_zero',
        // Normalize the video timeline too; copying the source stream can
        // preserve encoder delay that shifts it relative to processed audio.
        '-vf', 'setpts=PTS-STARTPTS',
        '-c:v', 'libx264', '-preset', 'fast', '-tune', 'zerolatency',
        '-bf', '0', '-crf', '18',
        '-pix_fmt', 'yuv420p',
        ...(path.extname(ctx.outputFile).toLowerCase() === '.mov'
          ? ['-c:a', 'pcm_s16le']
          : ['-c:a', 'aac', '-b:a', '192k']),
        '-shortest', ctx.outputFile]
      : ['-y', '-i', mixed, '-c:a', 'aac', ctx.outputFile];
    const output = await spawnAsync('ffmpeg', remuxArgs, {
      timeout: ctx.timeout || PROCESS_TIMEOUTS.FFMPEG_MS,
    });
    if (output.code !== 0) throw new Error(`pitchtransition output failed: ${output.stderr.slice(-500)}`);
  } finally {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
}

// ── Sidechain-gate vocoder ────────────────────────────────────────────

/**
 * Apply the SCGV vocoder. The input media is the modulator and the first
 * parameter is the carrier URL, followed by the positional vocoder options.
 *
 * Pipe syntax:
 *   scgv=<carrier_url>[;bandwidth;ratio;threshold;release;attack;makeup;knee;detection;range;volume;pitch]
 */
export async function applySidechainGateVocoder(
  ctx: ProcessorContext,
  params: string[],
): Promise<void> {
  const carrierUrl = params[0]?.trim();
  if (!carrierUrl) {
    throw new Error('scgv requires a carrier URL');
  }

  const numeric = (index: number): number | undefined => {
    const value = params[index];
    if (value === undefined || value.trim() === '') return undefined;
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : undefined;
  };

  const options = {
    url: carrierUrl,
    bandwidth: numeric(1),
    ratio: numeric(2),
    threshold: numeric(3),
    release: numeric(4),
    attack: numeric(5),
    makeup: numeric(6),
    knee: numeric(7),
    detection: params[8]?.trim() || undefined,
    range: numeric(9),
    volume: numeric(10),
    pitch: numeric(11),
  };

  const command = buildVocoderCommand(options);
  if (!command.ffmpegArgs) {
    throw new Error(command.usageHelp || 'scgv could not build an FFmpeg command');
  }

  const carrierDir = makeTempDir('scgv-carrier');
  const carrierExt = path.extname(new URL(carrierUrl).pathname) || '.mp3';
  const carrierPath = path.join(carrierDir, `carrier${carrierExt}`);

  try {
    await downloadUrl(carrierUrl, carrierPath);

    // Replace the builder's carrier URL with the downloaded local file.
    const carrierInputIndex = command.ffmpegArgs.indexOf(carrierUrl);
    if (carrierInputIndex < 0) {
      throw new Error('scgv command did not contain its carrier input');
    }
    const ffmpegArgs = [...command.ffmpegArgs];
    ffmpegArgs[carrierInputIndex] = carrierPath;

    await spawnAsync('ffmpeg', [
      '-loglevel', 'error',
      '-hide_banner',
      '-y',
      '-i', ctx.inputFile,
      ...ffmpegArgs,
      '-c:v', 'libx264',
      '-preset', 'fast',
      '-crf', '23',
      '-pix_fmt', 'yuv420p',
      '-c:a', 'aac',
      '-b:a', '192k',
      '-shortest',
      ctx.outputFile,
    ], { timeout: ctx.timeout || PROCESS_TIMEOUTS.FFMPEG_MS });
  } finally {
    cleanupDir(carrierDir);
  }
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
    const { width, height } = await getVideoDimensions(ctx.inputFile);
    filterChain = buildParametricMirrorFilter({
      angle: Number.isFinite(Number(first)) ? Number(first) : 90,
      percentX: Number.isFinite(Number(params[1])) ? Number(params[1]) : 0.5,
      percentY: Number.isFinite(Number(params[2])) ? Number(params[2]) : 0.5,
    }, width, height);
  }

  await spawnAsync('ffmpeg', [
    '-y', '-i', ctx.inputFile,
    '-vf', filterChain,
    '-c:a', 'copy',
    ctx.outputFile,
  ], { timeout: ctx.timeout || PROCESS_TIMEOUTS.FFMPEG_MS });
}

export interface MirrorOptions {
  angle: number;      // arg:0 - Rotation angle in degrees
  percentX?: number;  // arg:1 - Mirror line X offset (0.0 to 1.0, default 0.5)
  percentY?: number;  // arg:2 - Mirror line Y offset (0.0 to 1.0, default 0.5)
}

/**
 * Generates the complex FFmpeg filtergraph string for reflection/mirroring.
 * Rewritten 1:1 from the reference TypeScript pipe effect. The four named
 * side presets (left/right/top/bottom) are handled elsewhere and remain
 * unchanged for backwards compatibility.
 */
export function buildMirrorFilter({ angle, percentX = 0.5, percentY = 0.5 }: MirrorOptions): string {
  const radAngle = angle.toFixed(4);
  const px = percentX.toString();
  const py = percentY.toString();
  const lowerAngle = radAngle.toLowerCase();

  return [
    `-vf "rotate=(${lowerAngle})*PI/180:iw*2:ih*2,`,
    `geq='st(0,H/2+((${px})-0.5)*(W/2)*sin((${radAngle})*PI/180)+((${py})-0.5)*(H/2)*cos((${radAngle})*PI/180));`,
    `if(gte(Y,ld(0)),p(X,2*(ld(0))-Y),p(X,Y))',`,
    `rotate=(${lowerAngle})*-PI/180:$w:$h"`,
  ].join('');
}

/**
 * Pipe-compatible parametric mirror filter. Same math as buildMirrorFilter
 * but emitted as a bare -vf chain (no shell quoting) with concrete
 * dimensions substituted for $w/$h, plus a crop+format tail so the output
 * frame size and pixel format stay valid inside a coalesced filtergraph.
 */
export function buildParametricMirrorFilter(
  { angle, percentX = 0.5, percentY = 0.5 }: MirrorOptions,
  width = 1280,
  height = 720,
): string {
  const a = Number.isFinite(angle) ? angle : 90;
  const px = Number.isFinite(percentX) ? percentX : 0.5;
  const py = Number.isFinite(percentY) ? percentY : 0.5;
  const radAngle = a.toFixed(4);
  const lowerAngle = radAngle.toLowerCase();

  return [
    `rotate=(${lowerAngle})*PI/180:iw*2:ih*2`,
    `geq='st(0,H/2+((${px})-0.5)*(W/2)*sin((${radAngle})*PI/180)+((${py})-0.5)*(H/2)*cos((${radAngle})*PI/180));if(gte(Y,ld(0)),p(X,2*(ld(0))-Y),p(X,Y))'`,
    `rotate=(${lowerAngle})*-PI/180:${width}:${height}`,
    `crop=${width}:${height}`,
    'format=yuv420p',
  ].join(',');
}

/**
 * Probes the video file and processes the mirror filter using FFmpeg.
 * Standalone one-shot runner mirroring the reference pipe effect.
 */
export async function processVideoMirror(
  inputFile: string,
  outputFile: string,
  options: MirrorOptions,
): Promise<void> {
  // 1. Probe video metadata
  const probe = async (args: string[]): Promise<string> => {
    const result = await spawnAsync('ffprobe', args, { timeout: 10_000 });
    return result.stdout.trim();
  };
  const [w, h, fc, d] = await Promise.all([
    probe(['-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width', '-of', 'default=nw=1:nk=1', inputFile]),
    probe(['-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=height', '-of', 'default=nw=1:nk=1', inputFile]),
    probe(['-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=nb_frames', '-of', 'default=nokey=1:noprint_wrappers=1', inputFile]),
    probe(['-i', inputFile, '-show_entries', 'format=duration', '-v', 'quiet', '-of', 'csv=p=0']),
  ]);
  console.log(`Video Stats -> Width: ${w}, Height: ${h}, Frames: ${fc}, Duration: ${d}s`);

  // 2. Build FFmpeg command string, replacing $w/$h with probed metadata
  const filterCode = buildMirrorFilter(options).replace('$w', w).replace('$h', h);

  // 3. Execute FFmpeg process (tokenized so quoted geq math stays intact)
  console.log('Running FFmpeg command...');
  const result = await spawnAsync('ffmpeg', [
    '-y', '-i', inputFile,
    ...shellLikeSplit(filterCode),
    outputFile,
  ], { timeout: PROCESS_TIMEOUTS.FFMPEG_MS });
  if (result.code !== 0) throw new Error(result.stderr.slice(-1500) || 'FFmpeg mirror failed');
  console.log(`Successfully exported mirrored video to: ${outputFile}`);
}

export interface PinchPunchOptions {
  strength: number;   // Effect intensity (arg: 0)
  xScale?: number;    // X scale factor, defaults to 0.5 (arg: 1)
  yScale?: number;    // Y scale factor, defaults to 0.5 (arg: 2)
  xCenter?: number;   // Center X ratio (0.0 to 1.0), defaults to 0.5 (arg: 3)
  yCenter?: number;   // Center Y ratio (0.0 to 1.0), defaults to 0.5 (arg: 4)
}

/**
 * Generates an FFmpeg video filter string for a Pinch/Punch warp effect.
 * Rewritten 1:1 from the reference TypeScript pipe effect.
 */
export function buildPinchPunchFFmpegFilter(options: PinchPunchOptions): string {
  const {
    strength,
    xScale = 0.5,
    yScale = 0.5,
    xCenter = 0.5,
    yCenter = 0.5,
  } = options;

  // Mathematical warp expression adapted from FFmpeg geq filter logic
  const geqExpression =
    `p(` +
    `W*${xCenter}+((X-W*${xCenter})/(min(W,H)*0.5))*(1-((${strength}/4)*PI)*pow(1-pow(min(hypot((X-W*${xCenter})/(W*${xScale}),(Y-H*${yCenter})/(H*${yScale}))/1,1),2),2))*(min(W,H)*0.5),` +
    `H*${yCenter}+((Y-H*${yCenter})/(min(W,H)*0.5))*(1-((${strength}/4)*PI)*pow(1-pow(min(hypot((X-W*${xCenter})/(W*${xScale}),(Y-H*${yCenter})/(H*${yScale}))/1,1),2),2))*(min(W,H)*0.5)` +
    `)`;

  return `-vf format=yuv444p16le,"geq='${geqExpression}'",scale=iw:ih,format=yuv420p`;
}

/**
 * Pipe-compatible pinch&punch warp: identical geq math to
 * buildPinchPunchFFmpegFilter but returned as a bare filter chain (no -vf
 * prefix or shell quotes) so it can be coalesced with other pipe filters.
 */
export function buildPinchPunchPipeFilter(options: PinchPunchOptions): string {
  return buildPinchPunchFFmpegFilter(options)
    .replace(/^-vf\s+/, '')
    .replace(/"geq='([\s\S]*)'"/, "geq='$1'");
}

/**
 * Executes FFmpeg to apply the Pinch/Punch video filter to an input file.
 * Standalone one-shot runner mirroring the reference pipe effect.
 */
export async function applyPinchPunch(
  inputFile: string,
  outputFile: string,
  options?: PinchPunchOptions,
): Promise<void> {
  // Usage/Help check: if options are missing, log usage syntax
  if (!options) {
    console.log('Usage syntax: pinch&punch=<strength> [xScale] [yScale] [xCenter] [yCenter]');
    return;
  }

  const filterString = buildPinchPunchFFmpegFilter(options);

  try {
    const result = await spawnAsync('ffmpeg', [
      '-y', '-i', inputFile,
      ...shellLikeSplit(filterString),
      outputFile,
    ], { timeout: PROCESS_TIMEOUTS.FFMPEG_MS });
    if (result.code !== 0) throw new Error(result.stderr.slice(-1500) || 'FFmpeg pinch&punch failed');
  } catch (error) {
    console.error('Failed to process video with FFmpeg:', error);
    throw error;
  }
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
 * Accepts either a named preset or custom numeric parameters:
 *
 *   Preset:  params = ['largeWave']  (any key from WAVE_PRESETS)
 *   Custom:  params = ['custom:hSpeed', hFreq, hAmp, hPhase, vSpeed, vFreq, vAmp, vPhase, sep?, noclip?]
 *            OR the legacy positional form: params = [hSpeed, hFreq, hAmp, ...]
 *
 * Pipe-effect syntax examples:
 *   wave=largeWave
 *   wave=custom:0|15|0.8|0|0|0|0|0
 */
export async function applyWave(
  ctx: ProcessorContext,
  params: string[] = [],
): Promise<void> {
  // ── Named preset path ────────────────────────────────────────────────
  const firstParam = (params[0] ?? '').trim();

  if (firstParam in WAVE_PRESETS) {
    const filterChain = WAVE_PRESETS[firstParam as WavePresetKey];
    await spawnAsync('ffmpeg', [
      '-y', '-i', ctx.inputFile,
      '-vf', filterChain,
      '-c:a', 'copy',
      ctx.outputFile,
    ], { timeout: ctx.timeout || PROCESS_TIMEOUTS.FFMPEG_MS });
    return;
  }

  // ── Numeric / custom path ────────────────────────────────────────────
  // Strip optional "custom:" prefix from first param so wave=custom:1|2|3 works.
  let resolvedParams = params;
  if (firstParam.toLowerCase().startsWith('custom:')) {
    resolvedParams = [firstParam.slice('custom:'.length), ...params.slice(1)];
  }

  const parseBool = (val: string | undefined): boolean => {
    if (!val) return false;
    const s = String(val).toLowerCase().trim();
    return ['1', 'true', 't', 'y', 'yes', '+', 'on', 'sep', 'noclip'].includes(s);
  };
  const parseNum = (val: string | undefined, def: number): number => {
    const n = parseFloat(val || '');
    return Number.isNaN(n) ? def : n;
  };

  const hSpeed = parseNum(resolvedParams[0], 0);
  const hFreq = parseNum(resolvedParams[1], 0);
  const hAmp = parseNum(resolvedParams[2], 0);
  const hPhase = parseNum(resolvedParams[3], 0);
  const vSpeed = parseNum(resolvedParams[4], 0);
  const vFreq = parseNum(resolvedParams[5], 0);
  const vAmp = parseNum(resolvedParams[6], 0);
  const vPhase = parseNum(resolvedParams[7], 0);
  const separateWaves = parseBool(resolvedParams[8]);
  const noPixelClipping = parseBool(resolvedParams[9]);

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

  filterChain += 'scale=iw:ih,format=yuv420p';

  await spawnAsync('ffmpeg', [
    '-y', '-i', ctx.inputFile,
    '-vf', filterChain,
    '-c:a', 'copy',
    ctx.outputFile,
  ], { timeout: ctx.timeout || PROCESS_TIMEOUTS.FFMPEG_MS });
}

// ── TypeScript pipe engine ─────────────────────────────────────────────

/**
 * Public pipe names.  Keep this list in the effect module so validation and
 * execution cannot drift apart (the old TS bot had two separate lists).
 */
export const PIPE_EFFECT_NAMES = new Set([
  'hflip', 'vflip', 'invert', 'negate', 'grayscale', 'sepia', 'rotate',
  'ccshue', 'brightness', 'contrast', 'saturation', 'swapuv', 'mirror',
  'zoom', 'pinch&punch', 'p&p', 'pinchpunch', 'gm91deform', 'invertrgb',
  'invlum', 'volume', 'vibrato', 'areverse', 'vreverse', 'channelblend',
  'huehsv', 'multipitch', 'mp', 'multi', 'pitchtransition', 'pitchtrans',
  'multipitch2', 'mp2', 'multipitch3', 'mp3', 'lut', 'syncaudio', 'speed',
  'ffmpeg', 'frei0r', 'wave', 'wave2', 'tvsim', 'tv', 'swirl',
  'sierpinskiransomware', 'srw', 'preview1280', 'p1280', 'scale1280',
  'ytpmvscan', 'ytpmv', 'ytpmv_scan', 'oppositep1280', 'op1280',
  'earthquake', 'nbfx', 'ssmp', 'soundstretchmultipitch', 'multipitchsox',
  'mpsox', 'folkvalley', 'fv', 'labadjust', 'labadj', 'vocoder',
  'ilvocodex', 'orangevocoder', '4ormulator', 'audacity', 'magix',
  'alimiter', 'freakzinga', 'fzgm156', 'freakzingagm156', 'fgm156',
  'jitter', 'randomjitter', 'rj', 'trim', 'leftsplit', 'rightsplit',
  'ripple', 'scroll', 'pan', 'tile', 'watermark', 'ring', 'miui', 'reddit',
  'caption', 'orb', 'deorb', 'vebfisheye2', 'vebdefisheye2',
  'vebfisheye3', 'vebdefisheye3', 'chromashift', '🥸🥸', '﷽', '𒐫',
  'gm4', 'realgm4', 'acontrast', 'adestroy', 'audioequalizer', 'avflip',
  'nepeta', 'nparisonffmpeg', 'nineparisonffmpeg', 'wmm3dripple', 'wmm',
  'timecode', 'radar', 'freakzingatesteffect', 'fzte', 'freaktest',
  'stretch', 'gradientmap', 'gmap', 'spherize', 'sphere', 'bulge',
  'imagemagick', 'im', '(=)', '(<>)', 'geq', 'scgv',
  'sidechaingate_vocoder', 'caption',
]);

const PIPE_ALIASES: Record<string, string> = {
  p2p: 'pinch&punch',
  pnp: 'pinch&punch',
  gm: 'gradientmap',
  gmap: 'gradientmap',
  rj: 'randomjitter',
  mp: 'multipitch',
  multi: 'multipitch',
  tv: 'tvsim',
  fv: 'folkvalley',
  sphere: 'spherize',
  bulge: 'spherize',
  sidechaingate_vocoder: 'scgv',
};

export interface PipeEffect {
  name: string;
  params: string[];
}

function splitTopLevel(value: string, delimiters = ','): string[] {
  const result: string[] = [];
  let current = '';
  let parens = 0;
  let brackets = 0;
  let quote = '';
  for (const ch of value) {
    if (quote) {
      current += ch;
      if (ch === quote) quote = '';
      continue;
    }
    if (ch === "'" || ch === '"') { quote = ch; current += ch; continue; }
    if (ch === '(') parens += 1;
    if (ch === ')') parens = Math.max(0, parens - 1);
    if (ch === '[') brackets += 1;
    if (ch === ']') brackets = Math.max(0, brackets - 1);
    if (delimiters.includes(ch) && parens === 0 && brackets === 0) {
      if (current.trim()) result.push(current.trim());
      current = '';
    } else {
      current += ch;
    }
  }
  if (current.trim()) result.push(current.trim());
  return result;
}

function splitPipeParams(value: string): string[] {
  return value.trim().split(/[;|\s]+/).map((part) => part.trim()).filter(Boolean);
}

/**
 * Parse comma-separated pipe syntax while preserving commas inside
 * ffmpeg(...), geq expressions, and pitchtransition voice pairs.
 */
export function parsePipeEffects(raw: string): PipeEffect[] {
  const source = raw.trim();
  if (!source) return [];
  const parts = splitTopLevel(source, ',>');
  const effects: PipeEffect[] = [];
  for (const original of parts) {
    // Permit `wave=... volume=2` without making "volume" a wave parameter.
    const assignments = original
      .split(/\s+(?=[A-Za-z0-9_&()﷽𒐫🥸]+\s*=)/g)
      .map((part) => part.trim())
      .filter(Boolean);
    for (const part of assignments) {
      const rawWrapper = part.match(/^(ffmpeg|imagemagick|im)\s*\(([\s\S]*)\)$/i);
      if (rawWrapper) {
        effects.push({ name: rawWrapper[1]!.toLowerCase() === 'im' ? 'imagemagick' : rawWrapper[1]!.toLowerCase(), params: [rawWrapper[2]!.trim()] });
        continue;
      }
      const split = part.match(/^(leftsplit|rightsplit)\s*\(([\s\S]*)\)$/i);
      if (split) {
        effects.push({ name: split[1]!.toLowerCase(), params: [split[2]!.trim()] });
        continue;
      }
      const equals = part.indexOf('=');
      let name: string;
      let value: string;
      if (equals >= 0) {
        name = part.slice(0, equals).trim().toLowerCase();
        value = part.slice(equals + 1).trim();
      } else {
        const words = part.split(/\s+/);
        name = (words.shift() ?? '').toLowerCase();
        value = words.join(' ');
      }
      name = PIPE_ALIASES[name] ?? name;
      if (!name) continue;
      const params = name === 'pitchtransition' || name === 'pitchtrans'
        ? (value ? [value] : [])
        : name === 'scroll' && value.includes(':') && !value.includes('=')
          ? value.split(':').filter(Boolean)
          : value.includes('::')
            ? value.split('::').map((v) => v.trim()).filter(Boolean)
            : splitPipeParams(value);
      effects.push({ name, params });
    }
  }
  return effects;
}

function pipeNumber(params: string[], index: number, fallback: number): number {
  const value = Number(params[index]);
  return Number.isFinite(value) ? value : fallback;
}

function pipeBool(value: string | undefined): boolean {
  return ['1', 'true', 't', 'y', 'yes', '+', 'on', 'sep', 'noclip'].includes(
    (value ?? '').toLowerCase().trim(),
  );
}

function atempoChain(speed: number): string {
  const filters: string[] = [];
  let remaining = Math.max(0.01, Math.min(100, speed));
  while (remaining < 0.5) { filters.push('atempo=0.5'); remaining /= 0.5; }
  while (remaining > 2) { filters.push('atempo=2'); remaining /= 2; }
  filters.push(`atempo=${remaining.toFixed(6)}`);
  return filters.join(',');
}

function buildMultipitchAudio(params: string[]): string {
  const values = params
    .flatMap((param) => param.split(/[|,\s]+/))
    .map(Number)
    .filter(Number.isFinite)
    .slice(0, 16);
  const pitches = values.length ? values : [0];
  if (pitches.length === 1) {
    return `rubberband=tempo=1:pitch=${Math.pow(2, pitches[0]! / 12).toFixed(6)}`;
  }
  const labels = pitches.map((_, index) => `[p${index}]`).join('');
  const branches = pitches.map((pitch, index) =>
    `[p${index}]rubberband=tempo=1:pitch=${Math.pow(2, pitch / 12).toFixed(6)}[r${index}]`,
  ).join(';');
  const mixed = pitches.map((_, index) => `[r${index}]`).join('');
  return `asplit=${pitches.length}${labels};${branches};${mixed}amix=inputs=${pitches.length}:normalize=0`;
}

function buildPipeVideoFilter(
  name: string,
  params: string[],
  width: number,
  height: number,
): string | undefined {
  const n = name.toLowerCase();
  if (n === 'hflip') return 'hflip';
  if (n === 'vflip') return 'vflip';
  if (n === 'invert' || n === 'negate') return 'negate';
  if (n === 'grayscale') return 'hue=s=0';
  if (n === 'sepia') return 'colorchannelmixer=.393:.769:.189:0:.349:.686:.168:0:.272:.534:.131';
  if (n === 'rotate') return `rotate=${params[0] ?? '0'}`;
  if (n === 'brightness') return `eq=brightness=${params[0] ?? '0'}:contrast=${params[1] ?? '1'}:saturation=${params[2] ?? '1'}:gamma=${params[3] ?? '1'}`;
  if (n === 'contrast') return `eq=contrast=${params[0] ?? '1'}:brightness=${params[1] ?? '0'}:saturation=${params[2] ?? '1'}:gamma=${params[3] ?? '1'}`;
  if (n === 'saturation' || n === 'huehsv') return `hue=s=${params[0] ?? '1'}:h=${params[1] ?? '0'}`;
  if (n === 'swapuv') return 'swapuv';
  if (n === 'invertrgb') {
    const r = params[0] === '1' ? '0/1 1/0' : '0/0 1/1';
    const g = params[1] === '1' ? '0/1 1/0' : '0/0 1/1';
    const b = params[2] === '1' ? '0/1 1/0' : '0/0 1/1';
    return `curves=r='${r}':g='${g}':b='${b}'`;
  }
  if (n === 'mirror') {
    const first = (params[0] ?? '').toLowerCase();
    const aliases: Record<string, string> = { l: 'left', r: 'right', t: 'top', b: 'bottom' };
    const side = aliases[first] ?? first;
    if (['left', 'right', 'top', 'bottom'].includes(side)) {
      // These are the legacy presets; do not alter their behavior.
      return ({
        left: "split[_ma][_mb];[_ma]crop=iw/2:ih:0:0[_mL];[_mb]crop=iw/2:ih:0:0,hflip[_mR];[_mL][_mR]hstack",
        right: "split[_ma][_mb];[_ma]crop=iw/2:ih:iw/2:0,hflip[_mL];[_mb]crop=iw/2:ih:iw/2:0[_mR];[_mL][_mR]hstack",
        top: "split[_ma][_mb];[_ma]crop=iw:ih/2:0:0[_mT];[_mb]crop=iw:ih/2:0:0,vflip[_mB];[_mT][_mB]vstack",
        bottom: "split[_ma][_mb];[_ma]crop=iw:ih/2:0:ih/2,vflip[_mT];[_mb]crop=iw:ih/2:0:ih/2[_mB];[_mT][_mB]vstack",
      } as Record<string, string>)[side];
    }
    return buildParametricMirrorFilter({
      angle: pipeNumber(params, 0, 90),
      percentX: pipeNumber(params, 1, 0.5),
      percentY: pipeNumber(params, 2, 0.5),
    }, width, height);
  }
  if (n === 'pinch&punch' || n === 'p&p' || n === 'pinchpunch') {
    return buildPinchPunchPipeFilter({
      strength: pipeNumber(params, 0, 1),
      xScale: pipeNumber(params, 1, 0.5),
      yScale: pipeNumber(params, 2, 0.5),
      xCenter: pipeNumber(params, 3, 0.5),
      yCenter: pipeNumber(params, 4, 0.5),
    });
  }
  if (n === 'zoom') {
    const s = Math.max(0.01, pipeNumber(params, 0, 1.5));
    return `format=yuv444p,scale=iw*${s}:ih*${s},crop=iw/${s}:ih/${s}:(iw-iw/${s})/2:(ih-ih/${s})/2,format=yuv420p`;
  }
  if (n === 'scale1280' || n === 'preview1280' || n === 'p1280') return `scale=${params[0] ?? '1280'}:${params[1] ?? '-2'}`;
  if (n === 'pan') {
    const x = params[0] ?? '0';
    const y = params[1] ?? '0';
    return `format=yuv444p,geq='p(clip(X+(${x}),0,W-1),clip(Y+(${y}),0,H-1)):cb(clip(X+(${x}),0,W-1),clip(Y+(${y}),0,H-1)):cr(clip(X+(${x}),0,W-1),clip(Y+(${y}),0,H-1))',format=yuv420p`;
  }
  if (n === 'tile') {
    const x = params[0] ?? '2';
    const y = params[1] ?? '2';
    return `format=yuv444p,geq='p(mod(X*(${x}),W),mod(Y*(${y}),H)):cb(mod(X*(${x}),W),mod(Y*(${y}),H)):cr(mod(X*(${x}),W),mod(Y*(${y}),H))',format=yuv420p`;
  }
  if (n === 'ripple') {
    const speed = params[0] ?? '1';
    const freq = params[1] ?? '30';
    const amp = params[2] ?? '10';
    const phase = params[3] ?? '0';
    const r = 'hypot(X-W*0.5,Y-H*0.5)';
    const d = `(${r}+(${amp})*sin(2*PI*(${speed})*T-(${phase})-(${r})/(${freq}))`;
    const a = 'atan2(Y-H*0.5,X-W*0.5)';
    return `format=yuv444p,geq='p(W*0.5+(${d})*cos(${a}),H*0.5+(${d})*sin(${a}))',format=yuv420p`;
  }
  if (n === 'scroll') {
    if (params.some((p) => /^(hpos|vpos|ypos)=/i.test(p))) return `scroll=${params.join(',')}`;
    if (params.length >= 4) {
      const [x1, y1, x2, y2, duration] = params;
      const t = Number(duration) > 0 ? `T/${duration}` : 'T';
      const x = `(${x1})+((${x2})-(${x1}))*${t}`;
      const y = `(${y1})+((${y2})-(${y1}))*${t}`;
      return `format=yuv444p,geq='p(clip(X+${x},0,W-1),clip(Y+${y},0,H-1)):cb(clip(X+${x},0,W-1),clip(Y+${y},0,H-1)):cr(clip(X+${x},0,W-1),clip(Y+${y},0,H-1))',format=yuv420p`;
    }
    return `scroll=hpos=${params[0] ?? '0'}:vpos=${params[1] ?? '0'}`;
  }
  if (n === 'wave2') {
    const xw = params[0] ?? '3';
    const yw = params[1] ?? '3';
    const xa = params[2] ?? '20';
    const ya = params[3] ?? '20';
    const xp = params[4] ?? '0';
    const yp = params[5] ?? '0';
    const speed = params[6] ?? '0';
    const dx = `(${xa})*10*sin(2*PI*Y*(${xw})/2/H+2*PI*(${speed})*T+(${xp})*PI/180)`;
    const dy = `(${ya})*10*sin(2*PI*X*(${yw})/2/W+2*PI*(${speed})*T+(${yp})*PI/180)`;
    return `format=yuv444p,geq='p(clip(X+${dx},0,W-1),clip(Y+${dy},0,H-1)):cb(clip(X+${dx},0,W-1),clip(Y+${dy},0,H-1)):cr(clip(X+${dx},0,W-1),clip(Y+${dy},0,H-1))',format=yuv420p`;
  }
  if (n === 'randomjitter' || n === 'rj' || n === 'jitter') {
    const strength = params[0] ?? '10';
    return `rotate=0:iw*1.1:ih*1.1,format=yuv444p,geq='p(X+(${strength}/(25/3)/2.6666666666666665)*(2*mod(1000*sin(N*68),1)-1),Y+(${strength}/2.6666666666666665)*(2*mod(1000*sin(N+1000)*671,1)-1))',crop=${width}:${height},format=yuv420p`;
  }
  if (n === 'stretch') {
    const x = params[0] ?? '1.5';
    const y = params[1] ?? x;
    return `format=yuv444p,geq='p((W/2)+(X-W/2)/(${x}),(H/2)+(Y-H/2)/(${y}))',scale=${width}:${height},format=yuv420p`;
  }
  if (n === 'spherize' || n === 'sphere' || n === 'bulge') {
    const amount = params[0] ?? '0.8';
    const radius = params[1] ?? '0.5';
    const cx = params[2] ?? '0.5';
    const cy = params[3] ?? '0.5';
    const d = `hypot(X-W*${cx},Y-H*${cy})`;
    const scale = `max(1-(${amount})*(1-(${d}/(min(W,H)*${radius}))),0)`;
    return `format=yuv444p,geq='if(lte(${d},min(W,H)*${radius}),p(W*${cx}+(X-W*${cx})*${scale},H*${cy}+(Y-H*${cy})*${scale}),p(X,Y))',format=yuv420p`;
  }
  if (n === 'gm91deform') return `format=yuv444p,geq='p(X,Y)',format=yuv420p`;
  if (n === 'caption') {
    const text = params.join(' ').replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/:/g, '\\:');
    return `drawtext=text='${text}':fontsize=h/15:fontcolor=white:borderw=3:bordercolor=black:x=(w-text_w)/2:y=20`;
  }
  if (n === 'frei0r') return params[0] ? `frei0r=${params.join(':')}` : undefined;
  if (n === 'rotate') return `rotate=${params[0] ?? '0'}`;
  if (n === 'invlum') return 'negate';
  if (n === 'realgm4' || n === 'gm4') return "curves=all='0/0 0.5/1 1/0'";
  if (n === 'vebfisheye2') return Array.from({ length: Math.max(1, Math.min(10, pipeNumber(params, 0, 1))) }, () => 'v360=e:hammer').join(',');
  if (n === 'vebdefisheye2') return Array.from({ length: Math.max(1, Math.min(10, pipeNumber(params, 0, 1))) }, () => 'v360=hammer:e').join(',');
  if (n === 'vebfisheye3') return Array.from({ length: Math.max(1, Math.min(10, pipeNumber(params, 0, 1))) }, () => 'v360=fisheye:22:7').join(',');
  if (n === 'vebdefisheye3') return Array.from({ length: Math.max(1, Math.min(10, pipeNumber(params, 0, 1))) }, () => 'v360=22:fisheye:7').join(',');
  if (n === 'chromashift') return 'chromashift=cbh=5:crh=-5';
  if (n === '🥸🥸') return 'hue=h=3.14159265';
  if (n === '﷽') return 'v360=e:ball,v360=fisheye:22:7';
  if (n === '𒐫') return 'v360=ball:hammer';
  if (n === 'orb') return 'scroll=hpos=0.05,v360=e:hammer,v360=fisheye:22:7';
  if (n === 'deorb') return 'scroll=hpos=-0.05,v360=hammer:e,v360=22:fisheye:7';
  if (n === 'timecode') return "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf:timecode='00\\:00\\:00\\:00':rate=30:fontcolor=white:fontsize=h/24:box=1:boxcolor=black:x=(w-text_w)/1.1:y=(h-text_h)/1.12";
  if (n === '(=)') return 'v360=ball:e,hue=h=450*t/10,v360=e:9';
  if (n === '(<>)') return 'v360=e:9,hue=s=2*t/10,v360=9:e';
  if (n === 'tvsim' || n === 'tv') return `noise=alls=${params[0] ?? '8'}:allf=t+u,curves=all='0/0 0.5/0.7 1/1'`;
  if (n === 'sierpinskiransomware' || n === 'srw') return 'tile=2x2';
  if (n === 'radar') return 'waveform,format=yuv420p';
  if (n === 'nparisonffmpeg' || n === 'nineparisonffmpeg') return 'tile=2x2';
  return undefined;
}

function buildPipeAudioFilter(name: string, params: string[]): string | undefined {
  const n = name.toLowerCase();
  if (n === 'volume') return `volume=${params[0] ?? '1'}`;
  if (n === 'vibrato') return `vibrato=f=${params[0] ?? '5'}:d=${params[1] ?? '0.5'}`;
  if (n === 'areverse') return 'areverse,asetpts=PTS-STARTPTS';
  if (n === 'alimiter') return `alimiter=level_in=${params[0] ?? '1'}:limit=${params[1] ?? '1'}:attack=${params[2] ?? '5'}:release=${params[3] ?? '50'}:latency=${Math.max(0, Math.min(1, pipeNumber(params, 4, 1)))}`;
  if (n === 'acontrast') return `acontrast=${params[0] ?? '33'}`;
  if (n === 'adestroy') return 'acontrast=100,acontrast=100,acontrast=100,acontrast=100,acontrast=100';
  if (n === 'audioequalizer') {
    return ['40', '150', '375', '1000', '3000']
      .map((freq, index) => `equalizer=f=${freq}:width_type=q:width=1:g=${params[index] ?? '0'}`).join(',');
  }
  if (n === '4ormulator') return `rubberband=tempo=1:formant=${params[0] ?? '712923000'}:pitch=1`;
  if (n === 'multipitch' || n === 'mp' || n === 'multi' || n === 'multipitch2' || n === 'mp2') return buildMultipitchAudio(params);
  if (n === 'syncaudio') return 'aresample=async=1:first_pts=0';
  if (n === 'avflip') return 'aresample=44100,rubberband=tempo=0.05:window=long,afftfilt=real=real(1216000/b):imag=imag(1216000/b),rubberband=tempo=20:window=long,volume=8';
  if (n === 'speed') return atempoChain(pipeNumber(params, 0, 1));
  return undefined;
}

async function runPipeFfmpeg(
  inputFile: string,
  outputFile: string,
  videoFilter: string | undefined,
  audioFilter: string | undefined,
  timeout: number,
): Promise<void> {
  const args = ['-loglevel', 'error', '-hide_banner', '-y', '-i', inputFile,
    '-map', '0:v?', '-map', '0:a?'];
  if (videoFilter) args.push('-vf', videoFilter, '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '23', '-pix_fmt', 'yuv420p');
  else args.push('-c:v', 'copy');
  if (audioFilter) args.push('-af', audioFilter, '-c:a', 'aac', '-b:a', '160k');
  else args.push('-c:a', 'copy');
  args.push('-movflags', '+faststart', outputFile);
  const result = await spawnAsync('ffmpeg', args, { timeout });
  if (result.code !== 0) throw new Error(result.stderr.slice(-1500) || 'FFmpeg pipe step failed');
}

async function runPipeRaw(
  inputFile: string,
  outputFile: string,
  raw: string,
  timeout: number,
): Promise<void> {
  const args = shellLikeSplit(raw);
  if (!args.length) throw new Error('ffmpeg pipe effect requires arguments');
  const result = await spawnAsync('ffmpeg', [
    '-loglevel', 'error', '-hide_banner', '-y', '-i', inputFile,
    ...args, outputFile,
  ], { timeout });
  if (result.code !== 0) throw new Error(result.stderr.slice(-1500) || 'Raw FFmpeg pipe step failed');
}

async function runPipeOverlay(
  ctx: ProcessorContext,
  outputFile: string,
  url: string,
): Promise<void> {
  const dir = makeTempDir('pipe-overlay');
  const image = path.join(dir, 'overlay.png');
  try {
    await downloadUrl(url, image);
    const result = await spawnAsync('ffmpeg', [
      '-loglevel', 'error', '-hide_banner', '-y',
      '-i', ctx.inputFile, '-loop', '1', '-i', image,
      '-filter_complex', '[1:v]format=rgba[wm];[0:v][wm]overlay=0:0:shortest=1[v]',
      '-map', '[v]', '-map', '0:a?', '-c:v', 'libx264', '-preset', 'ultrafast',
      '-crf', '23', '-pix_fmt', 'yuv420p', '-c:a', 'copy', outputFile,
    ], { timeout: ctx.timeout || PROCESS_TIMEOUTS.FFMPEG_MS });
    if (result.code !== 0) throw new Error(result.stderr.slice(-1200) || 'Overlay failed');
  } finally {
    cleanupDir(dir);
  }
}

/**
 * Execute a pipe chain. Compatible video/audio filters are coalesced into a
 * single FFmpeg invocation, which is substantially faster than the old
 * one-process-per-effect behavior. Complex effects still get isolated steps.
 */
export async function applyPipeEffects(
  ctx: ProcessorContext,
  source: string | PipeEffect[],
): Promise<void> {
  const effects = typeof source === 'string' ? parsePipeEffects(source) : source;
  if (!effects.length) {
    const result = await spawnAsync('ffmpeg', ['-loglevel', 'error', '-hide_banner', '-y', '-i', ctx.inputFile, '-c', 'copy', ctx.outputFile], { timeout: ctx.timeout || PROCESS_TIMEOUTS.FFMPEG_MS });
    if (result.code !== 0) throw new Error(result.stderr.slice(-1200) || 'No-op FFmpeg copy failed');
    return;
  }
  const fs = await import('node:fs');
  const tmpDir = makeTempDir('pipe');
  let current = ctx.inputFile;
  try {
    let index = 0;
    while (index < effects.length) {
      const effect = effects[index]!;
      const output = index === effects.length - 1 ? ctx.outputFile : path.join(tmpDir, `pipe_${index}.mkv`);
      const name = effect.name.toLowerCase();

      if (name === 'ffmpeg') {
        await runPipeRaw(current, output, effect.params[0] ?? '', ctx.timeout || PROCESS_TIMEOUTS.FFMPEG_MS);
        current = output; index += 1; continue;
      }
      if (name === 'imagemagick' || name === 'im') {
        throw new Error('ImageMagick pipe effects require the ImageMagick runtime and are not available in the TypeScript runner');
      }
      if (name === 'leftsplit' || name === 'rightsplit') {
        const inner = effect.params[0] ?? '';
        const applyInner = (inputPath: string, outputPath: string) =>
          applyPipeEffects({ inputFile: inputPath, outputFile: outputPath, timeout: ctx.timeout }, inner);
        if (name === 'leftsplit') await applyLeftSplit({ inputFile: current, outputFile: output, timeout: ctx.timeout }, applyInner);
        else await applyRightSplit({ inputFile: current, outputFile: output, timeout: ctx.timeout }, applyInner);
        current = output; index += 1; continue;
      }
      if (name === 'gradientmap' || name === 'gmap') {
        await applyGradientmap({ inputFile: current, outputFile: output, timeout: ctx.timeout }, effect.params.join(' '));
        current = output; index += 1; continue;
      }
      if (name === 'scgv' || name === 'sidechaingate_vocoder') {
        await applySidechainGateVocoder({ inputFile: current, outputFile: output, timeout: ctx.timeout }, effect.params);
        current = output; index += 1; continue;
      }
      if (name === 'pitchtransition' || name === 'pitchtrans') {
        await applyPitchTransition({ inputFile: current, outputFile: output, timeout: ctx.timeout }, effect.params);
        current = output; index += 1; continue;
      }
      if (name === 'nepeta') {
        await applyNepeta({ inputFile: current, outputFile: output, timeout: ctx.timeout }, effect.params[0]);
        current = output; index += 1; continue;
      }
      if (['watermark', 'ring', 'miui', 'reddit'].includes(name)) {
        const urls: Record<string, string> = {
          ring: 'https://files.catbox.moe/r8l5ay.png',
          miui: 'https://files.catbox.moe/z0gkil.png',
          reddit: 'https://files.catbox.moe/3ce714.png',
        };
        const url = effect.params[0] || urls[name];
        if (!url) throw new Error('watermark requires an image URL');
        await runPipeOverlay({ inputFile: current, outputFile: output, timeout: ctx.timeout }, output, url);
        current = output; index += 1; continue;
      }
      if (name === 'trim') {
        const start = Number(effect.params[0] ?? 0);
        const end = Number(effect.params[1]);
        if (!Number.isFinite(start) || !Number.isFinite(end) || start < 0 || end <= start) {
          throw new Error('trim requires start and end timestamps');
        }
        const result = await spawnAsync('ffmpeg', [
          '-loglevel', 'error', '-hide_banner', '-y', '-ss', String(start), '-i', current,
          '-t', String(end - start), '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '23',
          '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '160k', output,
        ], { timeout: ctx.timeout || PROCESS_TIMEOUTS.FFMPEG_MS });
        if (result.code !== 0) throw new Error(result.stderr.slice(-1200) || 'trim failed');
        current = output; index += 1; continue;
      }

      // Coalesce adjacent ordinary effects into one filtergraph. This is the
      // hot path for chains such as negate,mirror=45,zoom=2,volume=1.2.
      const videoFilters: string[] = [];
      const audioFilters: string[] = [];
      let cursor = index;
      const dims = await getVideoDimensions(current);
      while (cursor < effects.length) {
        const next = effects[cursor]!;
        const nextName = next.name.toLowerCase();
        if (['ffmpeg', 'imagemagick', 'im', 'leftsplit', 'rightsplit', 'gradientmap', 'gmap', 'scgv', 'sidechaingate_vocoder', 'pitchtransition', 'pitchtrans', 'nepeta', 'watermark', 'ring', 'miui', 'reddit', 'trim'].includes(nextName)) break;
        if (nextName === 'wave' && next.params[0] && next.params[0] in WAVE_PRESETS) {
          videoFilters.push(WAVE_PRESETS[next.params[0] as WavePresetKey]!);
        } else if (nextName === 'wave') {
          const first = next.params[0] ?? '';
          const values = first.toLowerCase().startsWith('custom:') ? [first.slice(7), ...next.params.slice(1)] : next.params;
          const hSpeed = values[0] ?? '0';
          const hFreq = values[1] ?? '0';
          const hAmp = values[2] ?? '0';
          const hPhase = values[3] ?? '0';
          const vSpeed = values[4] ?? '0';
          const vFreq = values[5] ?? '0';
          const vAmp = values[6] ?? '0';
          const vPhase = values[7] ?? '0';
          const x = `X-((sin((T*5*${vSpeed}+(${vPhase}*15))+(Y/H)*(PI*${vFreq})))*(-15*${vAmp}*(W/640)))`;
          const y = `Y-((sin((T*5*${hSpeed}+(${hPhase}*15))+(X/W)*(PI*${hFreq})))*(-15*${hAmp}*(W/640)))`;
          videoFilters.push(`format=yuv444p,geq='p(${x},${y})',format=yuv420p`);
        } else if (nextName === 'speed') {
          videoFilters.push(`setpts=${(1 / Math.max(0.01, pipeNumber(next.params, 0, 1))).toFixed(6)}*PTS`);
          audioFilters.push(buildPipeAudioFilter(nextName, next.params)!);
        } else {
          const vf = buildPipeVideoFilter(nextName, next.params, dims.width, dims.height);
          const af = buildPipeAudioFilter(nextName, next.params);
          if (!vf && !af) break;
          if (vf) videoFilters.push(vf);
          if (af) audioFilters.push(af);
        }
        cursor += 1;
      }
      if (cursor === index) throw new Error(`Unsupported TypeScript pipe effect: ${effect.name}`);
      await runPipeFfmpeg(current, output, videoFilters.length ? videoFilters.join(',') : undefined, audioFilters.length ? audioFilters.join(',') : undefined, ctx.timeout || PROCESS_TIMEOUTS.FFMPEG_MS);
      current = output;
      index = cursor;
    }
    if (current !== ctx.outputFile && fs.existsSync(current)) fs.copyFileSync(current, ctx.outputFile);
  } finally {
    cleanupDir(tmpDir);
  }
}
