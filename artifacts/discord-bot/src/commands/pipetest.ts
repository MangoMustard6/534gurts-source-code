import { Message } from 'discord.js';
import path from 'path';
import fs from 'fs';
import { makeTempDir, cleanupDir, downloadUrl } from '../utils/temp.js';
import { getUploadLimitBytes, formatBytes } from '../utils/limits.js';
import { _upload_to_catbox } from '../utils/catbox.js';
import { applyGradientmap, applySidechainGateVocoder, applyWave } from '../effects.js';
import {
  parseGradientParams,
  parseGradientPointsText,
  resolveAttachment,
  maybeLoadGradientFileAttachment,
  SUPPORTED_VIDEO_EXTS,
  SUPPORTED_IMAGE_EXTS,
  GRADIENT_FILE_EXTS,
} from './gradientmap.js';
import { WAVE_PRESETS } from '../wavePresets.js';

const WAVE_PRESET_LIST = Object.keys(WAVE_PRESETS).map((k) => `\`${k}\``).join(', ');

const USAGE =
  '**Usage:** `th/pipetest <effect>` — attach or reply-to a video/image\n' +
  '**Effects:**\n' +
  `• \`wave=<preset>\` — ${WAVE_PRESET_LIST}\n` +
  '• `wave=custom:<hSpd>|<hFreq>|<hAmp>|<hPhase>|<vSpd>|<vFreq>|<vAmp>|<vPhase>`\n' +
  '• `gradientmap <R,G,B> <R,G,B> ...` — color gradient map\n' +
  '• `scgv=<carrier_url>[;bandwidth;ratio;threshold;release;attack;makeup;knee;detection;range;volume;pitch]` — sidechain-gate vocoder\n' +
  '**Examples:**\n' +
  '`th/pipetest wave=largeWave`\n' +
  '`th/pipetest wave=custom:0|15|0.8|0|0|0|0|0`\n' +
  '`th/pipetest gradientmap 0,0,0 255,255,255`';

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
  const tokens = tokenizeParams(rest);

  if (!tokens.length) {
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

  // ── Determine effect type ────────────────────────────────────────────────
  const firstToken = tokens[0];
  const firstLower = firstToken.toLowerCase();
  const isWave = firstLower.startsWith('wave=') || firstLower === 'wave';
  const isScgv = firstLower.startsWith('scgv=') || firstLower === 'scgv';

  const tmpDir = makeTempDir('pipetest');
  const startTime = Date.now();

  try {
    const inputPath = path.join(tmpDir, `input.${ext}`);
    const baseName = path.parse(name).name.replace(/\.[^.]+$/, '');
    const outSuffix = isImage ? `.${ext}` : '.mp4';
    const outputPath = path.join(tmpDir, `pipetest_${baseName}${outSuffix}`);

    await downloadUrl(url, inputPath);

    if (isWave) {
      // ── Wave effect ────────────────────────────────────────────────────
      let waveParams: string[];
      if (firstLower.startsWith('wave=')) {
        // wave=largeWave  or  wave=custom:1  (with rest of numeric params as separate tokens)
        waveParams = [firstToken.slice('wave='.length), ...tokens.slice(1)];
      } else {
        // bare 'wave' token — rest are numeric params
        waveParams = tokens.slice(1);
      }

      const presetLabel = waveParams[0] ?? 'custom';
      const status = await message.reply(`⏳ Applying wave effect \`${presetLabel}\`…`);

      await applyWave({ inputFile: inputPath, outputFile: outputPath }, waveParams);

      const elapsed = ((Date.now() - startTime) / 1000).toFixed(3);
      if (!fs.existsSync(outputPath) || fs.statSync(outputPath).size === 0) {
        await status.edit('❌ Wave effect produced no output.');
        return;
      }

      const outSize = fs.statSync(outputPath).size;
      const uploadLimit = getUploadLimitBytes(message.guild ?? null);
      if (outSize > uploadLimit) {
        await status.edit(`Output too large for Discord (${formatBytes(outSize)}). Uploading to Catbox…`);
        const catboxUrl = await _upload_to_catbox(outputPath);
        if (catboxUrl) {
          await status.edit(
            `✅ Wave \`${presetLabel}\` done! (${elapsed}s)\n-# Output exceeded Discord limit — uploaded to Catbox.\n${catboxUrl}`,
          );
        } else {
          await status.edit(`❌ Too large for Discord and Catbox upload failed. (${formatBytes(outSize)})`);
        }
        return;
      }

      await status.edit({
        content: `✅ Wave \`${presetLabel}\` applied!\n-# Took ${elapsed} seconds.`,
        files: [{ attachment: outputPath, name: path.basename(outputPath) }],
      });

    } else if (isScgv) {
      const vocoderParams = [
        firstLower.startsWith('scgv=') ? firstToken.slice('scgv='.length) : '',
        ...tokens.slice(1),
      ];
      const carrier = vocoderParams[0] || '(missing carrier)';
      const status = await message.reply(`⏳ Applying scgv vocoder with carrier \`${carrier.slice(0, 80)}\`…`);

      await applySidechainGateVocoder(
        { inputFile: inputPath, outputFile: outputPath },
        vocoderParams,
      );

      const elapsed = ((Date.now() - startTime) / 1000).toFixed(3);
      if (!fs.existsSync(outputPath) || fs.statSync(outputPath).size === 0) {
        await status.edit('❌ SCGV produced no output.');
        return;
      }

      const outSize = fs.statSync(outputPath).size;
      const uploadLimit = getUploadLimitBytes(message.guild ?? null);
      if (outSize > uploadLimit) {
        await status.edit(`Output too large for Discord (${formatBytes(outSize)}). Uploading to Catbox…`);
        const catboxUrl = await _upload_to_catbox(outputPath);
        await status.edit(
          catboxUrl
            ? `✅ SCGV done! (${elapsed}s)\n-# Output exceeded Discord limit — uploaded to Catbox.\n${catboxUrl}`
            : `❌ Too large for Discord and Catbox upload failed. (${formatBytes(outSize)})`,
        );
        return;
      }

      await status.edit({
        content: `✅ SCGV vocoder applied\n-# Took ${elapsed} seconds.`,
        files: [{ attachment: outputPath, name: 'sidechaingate_vocoder.mp4' }],
      });
    } else {
      // ── Gradientmap effect ─────────────────────────────────────────────
      let params = tokens;
      if (params.length && (params[0].startsWith('url:') || params[0].startsWith('http'))) {
        const loaded = await loadGradientPoints(params[0]);
        if (!loaded.ok) {
          await message.reply(`❌ ${loaded.error}`);
          return;
        }
        params = loaded.points;
      } else {
        // Skip a leading 'gradientmap'/'gm' keyword if present
        if (['gradientmap', 'gm', 'gmap'].includes(params[0]?.toLowerCase())) {
          params = params.slice(1);
        }
        const filePoints = await maybeLoadGradientFileAttachment(message, tmpDir);
        if (filePoints) params = filePoints;
      }

      const stopsResult = parseGradientParams(params);
      if (!stopsResult.ok) {
        await message.reply(`❌ ${stopsResult.error}`);
        return;
      }

      const status = await message.reply(`⏳ Applying gradient map (${stopsResult.stops.length} stops)…`);

      await applyGradientmap(
        { inputFile: inputPath, outputFile: outputPath },
        params.join(' '),
      );

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
    }
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    const elapsed = ((Date.now() - startTime) / 1000).toFixed(3);
    if (msg.includes('timed out')) {
      await message.reply(`❌ Processing timed out after ${elapsed}s.`);
    } else {
      await message.reply(`❌ \`${msg.slice(0, 300)}\`\n-# Took ${elapsed}s.`);
    }
  } finally {
    cleanupDir(tmpDir);
  }
}
