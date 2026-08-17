#!/usr/bin/env ts-node
/**
 * pitch.ts
 *
 * Combines pitch_transition.sh + video_pitch_mix.sh into one TypeScript CLI.
 *
 * - If the input is an audio file (mp3, wav, aac, ogg):
 *     applies a solo or multi-voice pitch sweep and writes the result as audio.
 * - If the input is a video file (mp4, mov, mkv, avi, webm, m4v):
 *     extracts its audio to WAV, runs the same pitch sweep on it, then muxes
 *     the pitched audio back into the video (video stream copied untouched).
 *
 * Usage:
 *   ts-node pitch.ts <input> <output> --pitch "<start1,end1>[;<start2,end2>;...]"
 *
 * Examples:
 *   Solo voice:
 *     ts-node pitch.ts in.wav out.wav --pitch "-5,9"
 *     ts-node pitch.ts in.mp4 out.mp4 --pitch "-5,9"
 *
 *   Multiple voices (rendered separately, then mixed together):
 *     ts-node pitch.ts in.mp4 out.mp4 --pitch "-5,9;5,-9"
 *
 * Requires ffmpeg and ffprobe to be available on PATH.
 * Compile with `tsc pitch.ts` and run with node, or run directly via ts-node.
 */

import { spawnSync } from "child_process";
import * as fs from "fs";
import * as os from "os";
import * as path from "path";

const SUPPORTED_AUDIO_EXT = ["mp3", "wav", "aac", "ogg"];
const SUPPORTED_VIDEO_EXT = ["mp4", "mov", "mkv", "avi", "webm", "m4v"];

interface Voice {
  start: number;
  end: number;
}

function fail(message: string): never {
  console.error(`ERROR: ${message}`);
  process.exit(1);
}

function run(cmd: string, args: string[]): void {
  const result = spawnSync(cmd, args, { stdio: ["ignore", "ignore", "pipe"] });
  if (result.error) {
    fail(`Failed to run ${cmd}: ${result.error.message}`);
  }
  if (result.status !== 0) {
    fail(`${cmd} exited with code ${result.status}: ${result.stderr.toString().trim()}`);
  }
}

function ffprobeDuration(file: string): number {
  const result = spawnSync("ffprobe", [
    "-v", "error",
    "-show_entries", "format=duration",
    "-of", "default=noprint_wrappers=1:nokey=1",
    file,
  ]);
  if (result.error || result.status !== 0) {
    fail(`Could not read duration of '${file}'.`);
  }
  const duration = parseFloat(result.stdout.toString().trim());
  if (Number.isNaN(duration)) {
    fail(`Could not parse duration of '${file}'.`);
  }
  return duration;
}

function hasAudioStream(file: string): boolean {
  const result = spawnSync("ffprobe", [
    "-v", "error",
    "-select_streams", "a",
    "-show_entries", "stream=index",
    "-of", "csv=p=0",
    file,
  ]);
  return result.status === 0 && result.stdout.toString().trim().length > 0;
}

function parsePitchArg(pitchArg: string): Voice[] {
  const voices = pitchArg.split(";").map((chunk) => chunk.trim()).filter(Boolean);
  if (voices.length === 0) {
    fail(`Invalid --pitch value '${pitchArg}'. Format: start,end[;start,end;...]`);
  }
  return voices.map((chunk) => {
    const parts = chunk.split(",").map((p) => p.trim());
    if (parts.length !== 2) {
      fail(`Invalid voice definition '${chunk}'. Expected format 'start,end'.`);
    }
    const start = parseFloat(parts[0]);
    const end = parseFloat(parts[1]);
    if (Number.isNaN(start) || Number.isNaN(end)) {
      fail(`Invalid voice definition '${chunk}'. Start/end must be numbers.`);
    }
    return { start, end };
  });
}

function buildAutomationFile(duration: number, voice: Voice, filePath: string): void {
  const lines: string[] = [];
  const step = 0.01;
  const steps = Math.floor(duration / step);
  for (let i = 0; i <= steps; i++) {
    const t = parseFloat((i * step).toFixed(2));
    const expr = `2^(((${t}/${duration})*((${voice.end})-(${voice.start}))+(${voice.start}))/12)`;
    lines.push(`${t} rubberband pitch ${expr};`);
  }
  fs.writeFileSync(filePath, lines.join("\n") + "\n");
}

function renderVoice(input: string, transFile: string, outWav: string): void {
  run("ffmpeg", [
    "-y", "-i", input,
    "-af", `asendcmd=f=${transFile},rubberband=phase=712923000`,
    outWav,
  ]);
}

/** Solo/multi-voice pitch sweep on an audio file. Writes result to `output`. */
function pitchTransition(input: string, output: string, pitchArg: string): void {
  const ext = path.extname(input).slice(1).toLowerCase();
  if (!SUPPORTED_AUDIO_EXT.includes(ext)) {
    fail(`Unsupported audio format '${ext}'. Supported formats are: ${SUPPORTED_AUDIO_EXT.join(", ")}.`);
  }

  const duration = ffprobeDuration(input);
  const voices = parsePitchArg(pitchArg);

  const workdir = fs.mkdtempSync(path.join(os.tmpdir(), "pitch-"));
  try {
    const voiceFiles: string[] = [];
    voices.forEach((voice, i) => {
      const transFile = path.join(workdir, `pitchtransition_${i}.txt`);
      buildAutomationFile(duration, voice, transFile);

      const voiceWav = path.join(workdir, `voice_${i}.wav`);
      renderVoice(input, transFile, voiceWav);
      voiceFiles.push(voiceWav);
    });

    if (voiceFiles.length === 1) {
      run("ffmpeg", ["-y", "-i", voiceFiles[0], output]);
    } else {
      const inputArgs = voiceFiles.flatMap((f) => ["-i", f]);
      run("ffmpeg", [
        "-y", ...inputArgs,
        "-filter_complex", `amix=inputs=${voiceFiles.length}:duration=longest:dropout_transition=0`,
        output,
      ]);
    }
  } finally {
    fs.rmSync(workdir, { recursive: true, force: true });
  }
}

/** Extracts a video's audio, pitch-sweeps it, and muxes it back in. */
function videoPitchMix(videoIn: string, videoOut: string, pitchArg: string): void {
  if (!hasAudioStream(videoIn)) {
    fail(`'${videoIn}' has no audio stream to extract.`);
  }

  const workdir = fs.mkdtempSync(path.join(os.tmpdir(), "video-pitch-"));
  try {
    const rawWav = path.join(workdir, "extracted.wav");
    console.log("Extracting audio to WAV...");
    run("ffmpeg", ["-y", "-i", videoIn, "-vn", "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2", rawWav]);

    const pitchedWav = path.join(workdir, "pitched.wav");
    console.log("Applying pitch transition...");
    pitchTransition(rawWav, pitchedWav, pitchArg);

    console.log("Muxing processed audio back into video...");
    run("ffmpeg", [
      "-y", "-i", videoIn, "-i", pitchedWav,
      "-map", "0:v:0", "-map", "1:a:0",
      "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
      "-shortest",
      videoOut,
    ]);
  } finally {
    fs.rmSync(workdir, { recursive: true, force: true });
  }
}

function main(): void {
  const args = process.argv.slice(2);
  if (args.length < 4) {
    fail(`Usage: ts-node pitch.ts <input> <output> --pitch "start,end[;start,end;...]"`);
  }
  const [input, output, flag, pitchArg] = args;

  if (flag !== "--pitch") {
    fail("The --pitch flag is required as the third argument.");
  }
  if (!fs.existsSync(input)) {
    fail(`Input file '${input}' not found.`);
  }

  const ext = path.extname(input).slice(1).toLowerCase();

  if (SUPPORTED_AUDIO_EXT.includes(ext)) {
    pitchTransition(input, output, pitchArg);
  } else if (SUPPORTED_VIDEO_EXT.includes(ext)) {
    videoPitchMix(input, output, pitchArg);
  } else {
    fail(
      `Unsupported file format '${ext}'. Supported audio: ${SUPPORTED_AUDIO_EXT.join(", ")}. ` +
        `Supported video: ${SUPPORTED_VIDEO_EXT.join(", ")}.`
    );
  }

  console.log(`Done. Output written to '${output}'.`);
}

main();
