import { Message } from 'discord.js';
import path from 'path';
import fs from 'fs';
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

// ── Gradient point parsing ───────────────────────────────────────────────────

function parseGradientPointsText(text: string): string[] {
  text = text.replace(/\r\n/g, '\n').replace(/\r/g, '\n').trim();
  if (!text) return [];

  // Try JSON first
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

  // Flat comma-separated list of numbers (5 per point)
  const flat = text.replace(/;/g, ',').split(',').map((s) => s.trim()).filter(Boolean);
  if (flat.length >= 10 && flat.length % 5 === 0) {
    const out: string[] = [];
    for (let i = 0; i < flat.length; i += 5) out.push(flat.slice(i, i + 5).join(','));
    return out;
  }

  // Line/semicolon based parsing
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

export function buildGradientmapFilter(params: string[]): { ok: true; vf: string } | { ok: false; error: string } {
  let rawPoints: string[] = [];
  const first = (params[0] ?? '').trim();

  if (first.startsWith('http://') || first.startsWith('https://') || first.startsWith('url:')) {
    // URL loading is async; caller must handle it. For inline/pipe use this is treated as one point.
    rawPoints = [first];
  } else if (params.length === 1 && first.startsWith('[[') && first.endsWith(']]')) {
    const inner = first.slice(2, -2).trim();
    rawPoints = inner.split(/\]\s*,\s*\[/).map((p) => p.trim().replace(/^[\[\]\s]+|[\[\]\s]+$/g, ''));
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

  // If every token is a bare number, reassemble into 5-value or 3-value groups.
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

  type Point = [r: number, g: number, b: number, a: number, pos: number | null];
  const points: Point[] = [];

  for (const p of rawPoints) {
    const parts = p.split(/[,;:_\s]+/).map((s) => s.trim()).filter(Boolean);
    if (parts.length < 3) return { ok: false, error: `gradientmap: invalid color point '${p}' — need at least R,G,B` };

    const nums = parts.map((s) => Number(s));
    if (nums.some(isNaN)) {
      return { ok: false, error: `gradientmap: invalid color point '${p}' — need R,G,B [A] [pos] numbers` };
    }
    const [r, g, b] = [Math.round(nums[0]!), Math.round(nums[1]!), Math.round(nums[2]!)];
    const a = nums[3] !== undefined ? Math.round(nums[3]) : 255;
    const pos = nums[4] !== undefined ? nums[4] : null;

    if ([r, g, b, a].some((v) => v < 0 || v > 255)) {
      return { ok: false, error: `gradientmap: color values in '${p}' must be 0-255` };
    }
    if (pos !== null && (pos < 0.0 || pos > 1.0)) {
      return { ok: false, error: `gradientmap: position in '${p}' must be 0.0-1.0` };
    }
    points.push([r, g, b, a, pos]);
  }

  const n = points.length;
  const posFor = (pt: Point, idx: number) => (pt[4] !== null ? pt[4] : idx / (n - 1));

  const curve = (channel: 0 | 1 | 2 | 3) =>
    points
      .map((pt, i) => `${posFor(pt, i).toFixed(4)}/${(pt[channel] / 255).toFixed(4)}`)
      .join(' ');

  const rCurve = curve(0);
  const gCurve = curve(1);
  const bCurve = curve(2);
  const aCurve = curve(3);

  const vf =
    `split=3[_gm_a][_gm_b][_gm_t];` +
    `[_gm_a]format=gray,curves=r='${rCurve}':g='${gCurve}':b='${bCurve}'[_gm_aa];` +
    `[_gm_b]format=gray,curves=all='${aCurve}'[_gm_bb];` +
    `[_gm_aa][_gm_bb]alphamerge[_gm_c];` +
    `[_gm_t][_gm_c]overlay`;

  return { ok: true, vf };
}

export async function applyGradientmap(
  inputPath: string,
  outputPath: string,
  params: string[],
  timeout?: number,
): Promise<{ ok: boolean; error: string }> {
  // If the first token is a URL, load points asynchronously now.
  let effectiveParams = params;
  const first = (params[0] ?? '').trim();
  if (first.startsWith('http://') || first.startsWith('https://') || first.startsWith('url:')) {
    const loaded = await loadGradientPoints(first);
    if (!loaded.ok) return { ok: false, error: loaded.error };
    effectiveParams = loaded.points;
  }

  const filterResult = buildGradientmapFilter(effectiveParams);
  if (!filterResult.ok) return { ok: false, error: filterResult.error };

  const result = await spawnAsync(
    'ffmpeg',
    [
      '-loglevel', 'error', '-hide_banner', '-y',
      '-i', inputPath,
      '-vf', filterResult.vf,
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
  // The first attachment is the media; look at the rest for a gradient file.
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
  // Tokenise respecting bracket groups so array syntax survives whitespace splitting.
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
    if (!params.length || params[0].startsWith('url:') || params[0].startsWith('http')) {
      /* keep as-is */ }
    else {
      const filePoints = await maybeLoadGradientFileAttachment(message, tmpDir);
      if (filePoints) params = filePoints;
    }

    const result = await applyGradientmap(inputPath, outputPath, params);
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
      content: `✅ Gradient map — ${params.length} color stops\n-# Took ${elapsed} seconds.`,
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
