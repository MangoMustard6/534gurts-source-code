import { Message } from 'discord.js';
import path from 'path';
import fs from 'fs';
import { makeTempDir, cleanupDir, downloadUrl } from '../utils/temp.js';
import { getUploadLimitBytes, formatBytes } from '../utils/limits.js';
import { _upload_to_catbox } from '../utils/catbox.js';
import { applyGradientmap, applyWave } from '../effects.js';
import {
  parseGradientParams,
  parseGradientPointsText,
  resolveAttachment,
  maybeLoadGradientFileAttachment,
  SUPPORTED_VIDEO_EXTS,
  SUPPORTED_IMAGE_EXTS,
  GRADIENT_FILE_EXTS,
} from './gradientmap.js';

const USAGE =
  '**Usage:** `th/pipetest <effect>=<params>` — attach or reply-to a video/image\n' +
  'Tests one pipe effect at a time. Supported effects: `gradientmap`, `wave`.\n' +
  '**Examples:**\n' +
  '`th/pipetest gradientmap 0,0,0 255,255,255`\n' +
  '`th/pipetest wave 1|2|3|4|5|6|7|8|true|false`';

function tokenizeParams(rest: string): string[] {
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
  return tokens.map((t) => t.trim()).filter(Boolean);
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
      return { ok: false, points: [], error: `pipetest: failed to download points from URL: ${msg}` };
    }
  }
  return { ok: true, points: [source], error: '' };
}

export async function handlePipetest(message: Message, rest: string): Promise<void> {
  const cleaned = tokenizeParams(rest);

  if (!cleaned.length) {
    await message.reply(USAGE);
    return;
  }

  const attachmentInfo = await resolveAttachment(message);
  if (!attachmentInfo) {
    await message.reply(`❌ Attach a video or image to use \`th/pipetest\`.\n${USAGE}`);
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

  const status = await message.reply(`⏳ Running pipe effect \`gradientmap\` (${cleaned.length} color stops)…`);
  const tmpDir = makeTempDir('pipetest');
  const startTime = Date.now();

  try {
    const inputPath = path.join(tmpDir, `input.${ext}`);
    const baseName = path.parse(name).name.replace(/\.[^.]+$/, '');
    const outSuffix = isImage ? `.${ext}` : '.mp4';
    const outputPath = path.join(tmpDir, `pipetest_${baseName}${outSuffix}`);

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

    await applyGradientmap(
      { inputFile: inputPath, outputFile: outputPath },
      params.join(' '),
    );

    const elapsed = ((Date.now() - startTime) / 1000).toFixed(3);
    if (!fs.existsSync(outputPath) || fs.statSync(outputPath).size === 0) {
      await status.edit('❌ Pipe effect produced no output.');
      return;
    }

    const outSize = fs.statSync(outputPath).size;
    const uploadLimit = getUploadLimitBytes(message.guild ?? null);
    if (outSize > uploadLimit) {
      await status.edit(`Output too large for Discord (${formatBytes(outSize)}). Uploading to Catbox…`);
      const catboxUrl = await _upload_to_catbox(outputPath);
      if (catboxUrl) {
        await status.edit(
          `✅ Pipe effect \`gradientmap\` done! (${elapsed}s)\n-# Output exceeded Discord limit — uploaded to Catbox.\n${catboxUrl}`,
        );
      } else {
        await status.edit(`❌ Too large for Discord and Catbox upload failed. (${formatBytes(outSize)})`);
      }
      return;
    }

    await status.edit({
      content: `✅ Pipe effect \`gradientmap\` — ${stopsResult.stops.length} color stops\n-# Took ${elapsed} seconds.`,
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
