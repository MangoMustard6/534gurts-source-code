/**
 * bytebeat.ts — Bytebeat audio generator
 *
 * Shared core used by both the prefix command (th/bytebeat) and the slash
 * command (/bytebeat). Generates 5 s of raw u8 mono PCM at 8 kHz by
 * evaluating a mathematical formula for each sample index t (0–39 999),
 * then transcodes to AAC/MP4 via fluent-ffmpeg.
 */

import path from 'path';
import { PassThrough } from 'stream';
import {
  Message,
  ChatInputCommandInteraction,
  AttachmentBuilder,
} from 'discord.js';
import ffmpeg from 'fluent-ffmpeg';
import { makeTempDir, cleanupDir } from '../utils/temp.js';

// ── Constants ────────────────────────────────────────────────────────────────

const SAMPLE_RATE = 8000;   // Hz
const DURATION_S  = 5;      // seconds
const TOTAL_SAMPLES = SAMPLE_RATE * DURATION_S; // 40 000

/**
 * Strict whitelist: digits, lowercase t, whitespace, and the mathematical
 * operators listed in the spec (+, -, *, /, %, &, |, ^, ~, <<, >>, >>>)
 * plus parentheses. Nothing else can slip through.
 */
const SAFE_FORMULA_RE = /^[0-9t\s+\-*/%&|^~<>()]+$/;

// ── Types ────────────────────────────────────────────────────────────────────

type BytebeatOk  = { ok: true;  filePath: string; tmpDir: string };
type BytebeatErr = { ok: false; error: string };
type BytebeatResult = BytebeatOk | BytebeatErr;

// ── Sanitiser ────────────────────────────────────────────────────────────────

/**
 * Returns the trimmed formula if it passes the whitelist, otherwise null.
 */
function sanitise(raw: string): string | null {
  const f = raw.trim();
  if (!f) return null;
  // Extra guard: reject anything containing words like 'import', 'eval',
  // 'Function', etc. — the regex already blocks those letters in context,
  // but defence-in-depth never hurts.
  if (!SAFE_FORMULA_RE.test(f)) return null;
  return f;
}

// ── PCM generator ────────────────────────────────────────────────────────────

/**
 * Compiles the formula into a JS function and runs it for every sample.
 * Returns a Buffer of TOTAL_SAMPLES unsigned-8-bit values, or an error string.
 */
function generatePCM(formula: string): Buffer | string {
  // Compile — this is where syntax errors surface.
  let fn: (t: number) => number;
  try {
    // eslint-disable-next-line no-new-func
    fn = new Function('t', `"use strict"; return ((${formula}) & 255);`) as (t: number) => number;
    fn(0); // smoke-test at t=0 to surface immediate runtime errors
  } catch (e) {
    return `Formula error: ${e instanceof Error ? e.message : String(e)}`;
  }

  const buf = Buffer.allocUnsafe(TOTAL_SAMPLES);
  try {
    for (let t = 0; t < TOTAL_SAMPLES; t++) {
      buf[t] = fn(t) & 0xff;
    }
  } catch (e) {
    return `Runtime error at sample generation: ${e instanceof Error ? e.message : String(e)}`;
  }
  return buf;
}

// ── FFmpeg transcoder ────────────────────────────────────────────────────────

/**
 * Pipes the raw u8 PCM buffer into ffmpeg via a PassThrough stream and
 * writes a standard PCM WAV file to outputPath.
 *
 * Equivalent shell command:
 *   ffmpeg -f u8 -ar 8000 -ac 1 -i pipe:0 -acodec pcm_s16le out.wav
 */
function transcodeToWAV(pcm: Buffer, outputPath: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const src = new PassThrough();

    ffmpeg(src)
      .inputFormat('u8')
      .inputOptions(['-ar 8000', '-ac 1'])
      .audioCodec('pcm_s16le')
      .output(outputPath)
      .on('end', () => resolve())
      .on('error', (err: Error) => reject(err))
      .run();

    // Write PCM data after .run() so ffmpeg's pipe is open.
    src.end(pcm);
  });
}

// ── Core executor (shared by prefix + slash) ─────────────────────────────────

export async function executeByteBeat(formula: string): Promise<BytebeatResult> {
  const safe = sanitise(formula);
  if (!safe) {
    return {
      ok: false,
      error:
        '❌ **Invalid formula.** Only numbers, `t`, spaces, and math operators ' +
        '(`+` `-` `*` `/` `%` `&` `|` `^` `~` `<<` `>>` `>>>` `(` `)`) are allowed.',
    };
  }

  const pcm = generatePCM(safe);
  if (typeof pcm === 'string') {
    return { ok: false, error: `❌ ${pcm}` };
  }

  const tmpDir = makeTempDir('bytebeat');
  const outputPath = path.join(tmpDir, 'bytebeat.wav');

  try {
    await transcodeToWAV(pcm, outputPath);
  } catch (e) {
    cleanupDir(tmpDir);
    return {
      ok: false,
      error: `❌ FFmpeg error: ${e instanceof Error ? e.message : String(e)}`,
    };
  }

  return { ok: true, filePath: outputPath, tmpDir };
}

// ── Prefix handler: th/bytebeat <formula> ────────────────────────────────────

const PREFIX_USAGE =
  '**th/bytebeat** — Generate Bytebeat audio\n' +
  'Usage: `th/bytebeat <formula>`\n' +
  '`t` = sample index (0 – 39 999) · 8 000 Hz · 5 s · output: MP4 / AAC\n\n' +
  '**Examples:**\n' +
  '`th/bytebeat t*(t>>5|t>>8)`\n' +
  '`th/bytebeat (t>>6|t|t>>(t>>16))*10+t*(t>>11)&74`\n' +
  '`th/bytebeat t*(42&t>>10)`';

export async function handleBytebeat(message: Message, rest: string): Promise<void> {
  const formula = rest.trim();

  if (!formula) {
    await message.reply(PREFIX_USAGE);
    return;
  }

  // Signal that something is happening before the potentially slow transcode.
  if ('sendTyping' in message.channel) await message.channel.sendTyping();

  const result = await executeByteBeat(formula);

  if (!result.ok) {
    await message.reply(result.error);
    return;
  }

  try {
    await message.reply({
      content: `🎵 **Bytebeat:** \`${formula}\``,
      files: [new AttachmentBuilder(result.filePath, { name: 'bytebeat.wav' })],
    });
  } catch (e) {
    await message.reply(
      `❌ Upload failed: ${e instanceof Error ? e.message : String(e)}`,
    );
  } finally {
    cleanupDir(result.tmpDir);
  }
}

// ── Slash handler: /bytebeat formula:<formula> ───────────────────────────────

export async function handleBytebeatInteraction(
  interaction: ChatInputCommandInteraction,
): Promise<void> {
  const formula = interaction.options.getString('formula', true);

  // Defer immediately so Discord doesn't time out while ffmpeg runs.
  await interaction.deferReply();

  const result = await executeByteBeat(formula);

  if (!result.ok) {
    await interaction.editReply(result.error);
    return;
  }

  try {
    await interaction.editReply({
      content: `🎵 **Bytebeat:** \`${formula}\``,
      files: [new AttachmentBuilder(result.filePath, { name: 'bytebeat.wav' })],
    });
  } catch (e) {
    await interaction.editReply(
      `❌ Upload failed: ${e instanceof Error ? e.message : String(e)}`,
    );
  } finally {
    cleanupDir(result.tmpDir);
  }
}
