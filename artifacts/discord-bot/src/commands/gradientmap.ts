import { execSync } from 'node:child_process';
import { Message } from 'discord.js';
import path from 'path';
import fs from 'fs';
import { pathToFileURL } from 'node:url';
import { spawnAsync } from '../utils/spawn.js';
import { makeTempDir, cleanupDir, downloadUrl } from '../utils/temp.js';
import { getUploadLimitBytes, formatBytes } from '../utils/limits.js';
import { PROCESS_TIMEOUTS } from '../config.js';
import { _upload_to_catbox } from '../utils/catbox.js';

const USAGE =
  '**Usage:** `th/gradientmap <R,G,B [A] [pos]> ...` *(alias: gm, gmap)* — attach or reply-to a video/image\n' +
  '**Examples:**\n' +
  '`th/gradientmap 0,0,0 255,255,255`\n' +
  '`th/gradientmap 0,0,0,255,0.0 255,0,0,255,0.5 255,255,255,128,1.0`\n' +
  '`th/gradientmap 0:0:0:255:0;255:0:0:255:0.5`\n' +
  '`th/gradientmap url:https://example.com/gradient.txt`\n' +
  'Attach a `.txt`/`.csv`/`.json`/`.gradient` gradient file alongside the media for unlimited stops.';

const SUPPORTED_VIDEO_EXTS = new Set(['mp4', 'mov', 'mkv', 'webm', 'avi']);
const SUPPORTED_IMAGE_EXTS = new Set(['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'tiff', 'avif']);
const GRADIENT_FILE_EXTS = new Set(['.txt', '.csv', '.json', '.gradient']);

// ── Core gradient filter (standalone reference implementation) ─────────────────

// Define a type for a color stop: [R, G, B, Alpha?, Position?]
export type ColorStop = [number, number, number, number?, number?];

export interface GradientMapOptions {
  inputFile: string;
  outputFile: string;
  colors: ColorStop[];
}

function normalizeStops(
  colors: ColorStop[],
): { r: number; g: number; b: number; a: number; pos: number }[] {
  return colors.map((c, i) => {
    const r = c[0];
    const g = c[1];
    const b = c[2];
    const a = c[3] !== undefined ? c[3] : 255;
    const pos = c[4] !== undefined ? c[4] : i / Math.max(colors.length - 1, 1);
    return { r, g, b, a, pos };
  });
}

export function buildGradientmapFilter(stops: ColorStop[]): string {
  const colors = normalizeStops(stops);

  const rCurve = colors.map((c) => `${c.pos}/${c.r / 255}`).join(' ');
  const gCurve = colors.map((c) => `${c.pos}/${c.g / 255}`).join(' ');
  const bCurve = colors.map((c) => `${c.pos}/${c.b / 255}`).join(' ');
  const aCurve = colors.map((c) => `${c.pos}/${c.a / 255}`).join(' ');

  return (
    `split=3[_gm_a][_gm_b][_gm_t];` +
    `[_gm_a]format=gray,curves=r=${rCurve}:g=${gCurve}:b=${bCurve}[_gm_aa];` +
    `[_gm_b]format=gray,curves=all=${aCurve}[_gm_bb];` +
    `[_gm_aa][_gm_bb]alphamerge[_gm_c];` +
    `[_gm_t][_gm_c]overlay`
  );
}

/**
 * Synchronous standalone entrypoint — runs FFmpeg directly.
 * Useful for CLI/scripts; the Discord bot uses applyGradientmap() instead.
 */
export function applyGradientMap({ inputFile, outputFile, colors }: GradientMapOptions): void {
  if (!fs.existsSync(inputFile)) {
    throw new Error(`Input file not found: ${inputFile}`);
  }
  if (colors.length === 0) {
    throw new Error('You must provide at least one color stop.');
  }

  const vf = buildGradientmapFilter(colors);
  const outputDir = path.dirname(path.resolve(outputFile));
  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }

  const ffmpegCmd = `ffmpeg -y -i "${inputFile}" -vf "${vf}" -pix_fmt yuv420p "${outputFile}"`;
  console.log(`\nExecuting FFmpeg command:\n${ffmpegCmd}\n`);

  try {
    execSync(ffmpegCmd, { stdio: 'inherit' });
    console.log(`\nSuccess! Created: ${outputFile}`);
  } catch (error) {
    console.error('\nError executing FFmpeg:', error);
    process.exit(1);
  }
}

// ── Gradient point parsing (Discord input formats) ────────────────────────────

function parseGradientPointsText(text: string): string[] {
  text = text.replace(/\r\n/g, '\n').replace(/\r/g, '\n').trim();
  if (!text) return [];

  try {
    const data = JSON.parse(text);
    if (Array.isArray(data) && data.length >= 2) {
      const points: string[] = [];
      for (const item of data) {
        if (Array.isArray(item)) points.push(item.map(String).join(','));
        else if (typeof item === 'string') points.push(item);
      }
      if (points.length) return points;
    }
  } catch { /* ignore */ }

  const flat = text.replace(/;/g, ',').split(',').map((s) => s.trim()).filter(Boolean);
  if (flat.length >= 10 && flat.length % 5 === 0) {
    const out: string[] = [];
    for (let i = 0; i < flat.length; i += 5) out.push(flat.slice(i, i + 5).join(','));
    return out;
  }

  const points: string[] = [];
  for (const rawLine of text.split('\n')) {
    let line = rawLine.trim();
    if (!line || line.startsWith('#')) continue;
    const hashIdx = line.indexOf('#');
    if (hashIdx !== -1) line = line.slice(0, hashIdx).trim();
    for (const segment of line.split(';')) {
      const s = segment.trim().replace(/^[\[\]\s]+|[\[\]\s]+$/g, '');
      if (s && !s.startsWith('#')) points.push(s);
    }
  }
  return points;
}

async function loadGradientPoints(source: string): Promise<{ ok: boolean; points: string[]; error: string }> {
  source = source.trim();
  if (source.startsWith('url:')) source = source.slice(4).trim();
  if (source.startsWith('http://') || source.startsWith('https://')) {
    const tmp = path.join(makeTempDir('gmurl'), 'gradient.txt');
    try {
      await downloadUrl(source, tmp);
      const text = fs.readFileSync(tmp, 'utf-8');
      return { ok: true, points: parseGradientPointsText(text), error: '' };
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      return { ok: false, points: [], error: `gradientmap: failed to download points from URL: ${msg}` };
    }
  }
  return { ok: true, points: [source], error: '' };
}

export function parseGradientParams(
  params: string[],
): { ok: true; stops: ColorStop[] } | { ok: false; error: string } {
  let rawPoints: string[] = [];
  const first = (params[0] ?? '').trim();

  if (first.startsWith('http://') || first.startsWith('https://') || first.startsWith('url:')) {
    rawPoints = [first];
  } else if (params.length === 1 && first.startsWith('[[') && first.endsWith(']]')) {
    const inner = first.slice(2, -2).trim();
    rawPoints = inner
      .split(/\]\s*,\s*\[/)
      .map((p) => p.trim().replace(/^[\[\]\s]+|[\[\]\s]+$/g, ''));
  } else if (params.length === 1 && first.startsWith('[') && first.endsWith(']')) {
    const bracketed = [...first.matchAll(/\[([^\]]+)\]/g)].map((m) => m[1]!.trim());
    if (bracketed.length >= 2) {
      rawPoints = bracketed;
    } else {
      const inner = first.slice(1, -1).trim();
      rawPoints = parseGradientPointsText(inner);
    }
  } else {
    rawPoints = params.map((p) => p.trim());
  }

  rawPoints = rawPoints.map((p) => p.replace(/^[\[\]\s\t]+|[\[\]\s\t]+$/g, '')).filter(Boolean);

  if (rawPoints.length && rawPoints.every((p) => /^-?\d+(\.\d+)?([eE][+-]?\d+)?$/.test(p))) {
    if (rawPoints.length % 5 === 0) {
      const grouped: string[] = [];
      for (let i = 0; i < rawPoints.length; i += 5) grouped.push(rawPoints.slice(i, i + 5).join(','));
      rawPoints = grouped;
    } else if (rawPoints.length % 3 === 0) {
      const grouped: string[] = [];
      for (let i = 0; i < rawPoints.length; i += 3) grouped.push(rawPoints.slice(i, i + 3).join(','));
      rawPoints = grouped;
    }
  }

  if (rawPoints.length < 2) {
    const preview = rawPoints.length ? rawPoints.slice(0, 5).map((p) => `'${p}'`).join(', ') : '(none)';
    return { ok: false, error: `gradientmap needs ≥2 points; got ${rawPoints.length}: ${preview}` };
  }

  const stops: ColorStop[] = [];
  for (const p of rawPoints) {
    const parts = p.split(/[,;:_\s]+/).map((s) => s.trim()).filter(Boolean);
    if (parts.length < 3) return { ok: false, error: `gradientmap: invalid color point '${p}' — need at least R,G,B` };

    const nums = parts.map((s) => Number(s));
    if (nums.some(isNaN)) {
      return { ok: false, error: `gradientmap: invalid color point '${p}' — need R,G,B [A] [pos] numbers` };
    }
    const [r, g, b] = [Math.round(nums[0]!), Math.round(nums[1]!), Math.round(nums[2]!)];
    const a = nums[3] !== undefined ? Math.round(nums[3]) : 255;
    const pos = nums[4] !== undefined ? nums[4] : undefined;

    if ([r, g, b, a].some((v) => v < 0 || v > 255)) {
      return { ok: false, error: `gradientmap: color values in '${p}' must be 0-255` };
    }
    if (pos !== undefined && (pos < 0.0 || pos > 1.0)) {
      return { ok: false, error: `gradientmap: position in '${p}' must be 0.0-1.0` };
    }
    stops.push(pos !== undefined ? [r, g, b, a, pos] : [r, g, b, a]);
  }

  return { ok: true, stops };
}

export async function applyGradientmap(
  inputPath: string,
  outputPath: string,
  stops: ColorStop[],
  timeout?: number,
): Promise<{ ok: boolean; error: string }> {
  const vf = buildGradientmapFilter(stops);

  const result = await spawnAsync(
    'ffmpeg',
    [
      '-loglevel', 'error', '-hide_banner', '-y',
      '-i', inputPath,
      '-vf', vf,
      '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
      '-pix_fmt', 'yuv420p',
      '-c:a', 'copy',
      outputPath,
    ],
    { timeout: timeout ?? PROCESS_TIMEOUTS.FFMPEG_MS },
  );

  return { ok: result.code === 0, error: result.stderr.slice(-1500) };
}

// ── Command handler ──────────────────────────────────────────────────────────

async function resolveAttachment(
  message: Message,
): Promise<{ url: string; name: string; ext: string } | null> {
  const direct = message.attachments.first();
  if (direct) {
    const ext = (direct.name?.split('.').pop() ?? '').toLowerCase();
    return { url: direct.url, name: direct.name ?? 'input.mp4', ext };
  }
  if (message.reference?.messageId) {
    try {
      const ref = await message.fetchReference();
      const a = ref.attachments.first();
      if (a) {
        const ext = (a.name?.split('.').pop() ?? '').toLowerCase();
        return { url: a.url, name: a.name ?? 'input.mp4', ext };
      }
    } catch { /* ignore */ }
  }
  return null;
}

async function maybeLoadGradientFileAttachment(
  message: Message,
  tmpDir: string,
): Promise<string[] | null> {
  const all = [...message.attachments.values()];
  if (!all.length) return null;
  for (let i = 1; i < all.length; i++) {
    const att = all[i]!;
    const ext = path.extname(att.name ?? '').toLowerCase();
    if (GRADIENT_FILE_EXTS.has(ext)) {
      const gradPath = path.join(tmpDir, `gradient_points${ext}`);
      try {
        await downloadUrl(att.url, gradPath);
        const text = fs.readFileSync(gradPath, 'utf-8');
        return parseGradientPointsText(text);
      } catch (e) {
        const msg = e instanceof Error ? e.message : String(e);
        throw new Error(`Failed to read gradient file attachment: ${msg}`);
      }
    }
  }
  return null;
}

export async function handleGradientmap(message: Message, rest: string): Promise<void> {
  const tokens: string[] = [];
  let cur = '';
  let depth = 0;
  for (const ch of rest.trim()) {
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
    await message.reply(USAGE);
    return;
  }

  const attachmentInfo = await resolveAttachment(message);
  if (!attachmentInfo) {
    await message.reply(`❌ Attach a video or image to use \`th/gradientmap\`.\n${USAGE}`);
    return;
  }

  const { url, name, ext } = attachmentInfo;
  const isVideo = SUPPORTED_VIDEO_EXTS.has(ext);
  const isImage = SUPPORTED_IMAGE_EXTS.has(ext);
  if (!isVideo && !isImage) {
    await message.reply(
      `❌ Unsupported file type \`.${ext}\`. Attach a video or image.\n${USAGE}`,
    );
    return;
  }

  const status = await message.reply(`⏳ Applying gradient map (${cleaned.length} color stops)…`);
  const tmpDir = makeTempDir('gradientmap');
  const startTime = Date.now();

  try {
    const inputPath = path.join(tmpDir, `input.${ext}`);
    const baseName = path.parse(name).name.replace(/\.[^.]+$/, '');
    const outSuffix = isImage ? `.${ext}` : '.mp4';
    const outputPath = path.join(tmpDir, `gradientmap_${baseName}${outSuffix}`);

    await downloadUrl(url, inputPath);

    let params = cleaned;
    if (params.length && (params[0].startsWith('url:') || params[0].startsWith('http'))) {
      const loaded = await loadGradientPoints(params[0]);
      if (!loaded.ok) {
        await status.edit(`❌ ${loaded.error}`);
        return;
      }
      params = loaded.points;
    } else {
      const filePoints = await maybeLoadGradientFileAttachment(message, tmpDir);
      if (filePoints) params = filePoints;
    }

    const stopsResult = parseGradientParams(params);
    if (!stopsResult.ok) {
      await status.edit(`❌ ${stopsResult.error}`);
      return;
    }

    const result = await applyGradientmap(inputPath, outputPath, stopsResult.stops);
    if (!result.ok) {
      await status.edit(`❌ Gradient map failed:\n\`\`\`\n${result.error.slice(-1500)}\n\`\`\``);
      return;
    }

    const elapsed = ((Date.now() - startTime) / 1000).toFixed(3);
    if (!fs.existsSync(outputPath) || fs.statSync(outputPath).size === 0) {
      await status.edit('❌ Gradient map produced no output.');
      return;
    }

    const outSize = fs.statSync(outputPath).size;
    const uploadLimit = getUploadLimitBytes(message.guild ?? null);
    if (outSize > uploadLimit) {
      await status.edit(`Output too large for Discord (${formatBytes(outSize)}). Uploading to Catbox…`);
      const catboxUrl = await _upload_to_catbox(outputPath);
      if (catboxUrl) {
        await status.edit(
          `✅ Gradient map done! (${elapsed}s)\n-# Output exceeded Discord limit — uploaded to Catbox.\n${catboxUrl}`,
        );
      } else {
        await status.edit(`❌ Too large for Discord and Catbox upload failed. (${formatBytes(outSize)})`);
      }
      return;
    }

    await status.edit({
      content: `✅ Gradient map — ${stopsResult.stops.length} color stops\n-# Took ${elapsed} seconds.`,
      files: [{ attachment: outputPath, name: path.basename(outputPath) }],
    });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    const elapsed = ((Date.now() - startTime) / 1000).toFixed(3);
    if (msg.includes('timed out')) {
      await status.edit(`❌ Processing timed out after ${elapsed}s.`);
    } else {
      await status.edit(`❌ \`${msg.slice(0, 300)}\`\n-# Took ${elapsed}s.`);
    }
  } finally {
    cleanupDir(tmpDir);
  }
}

// --- CLI Entrypoint (run with `tsx artifacts/discord-bot/src/commands/gradientmap.ts`) ---
if (import.meta.url === pathToFileURL(process.argv[1]!).href) {
  const inputFile = 'input.mp4';
  const outputFile = './output/gradient_map.mp4';
  const rawArgs = process.argv.slice(2);

  if (rawArgs.length === 0) {
    console.log('=========================================================================');
    console.log('FFmpeg Unlimited Gradient Map Generator');
    console.log('=========================================================================');
    console.log('Usage: tsx gradientmap.ts <Color1> <Color2> ... <ColorN>');
    console.log('Format: R,G,B[,Alpha,Position]');
    console.log('\nExamples:');
    console.log('  tsx gradientmap.ts 0,0,0 255,128,0 255,255,255');
    console.log('  tsx gradientmap.ts 0,0,0,255,0 0,0,255,128,0.3 255,255,255,255,1');
    console.log('=========================================================================');
    process.exit(0);
  }

  try {
    const colorArgs: ColorStop[] = rawArgs.map((arg, idx) => {
      const parts = arg.split(',').map(Number);
      if (parts.length < 3 || parts.some(isNaN)) {
        throw new Error(
          `Invalid color block at index ${idx}: "${arg}". Must be formatted as R,G,B[,A,Pos] using numbers.`,
        );
      }
      return [parts[0], parts[1], parts[2], parts[3], parts[4]] as ColorStop;
    });

    console.log(`Loaded ${colorArgs.length} color points. Mapping gradient...`);
    applyGradientMap({ inputFile, outputFile, colors: colorArgs });
  } catch (err: any) {
    console.error(`\nError: ${err.message}`);
    process.exit(1);
  }
}
