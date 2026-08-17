import { execSync } from 'node:child_process';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { pathToFileURL } from 'node:url';

export interface WaveFilterOptions {
  inputFile: string;
  outputFile: string;
  // Y-axis wave parameters
  arg0?: number; // Speed
  arg1?: number; // Frequency
  arg2?: number; // Amplitude
  arg3?: number; // Phase offset
  // X-axis wave parameters
  arg4?: number; // Speed
  arg5?: number; // Frequency
  arg6?: number; // Amplitude
  arg7?: number; // Phase offset
  // Boolean flags
  separateWaves: string | number | boolean;
  noPixelClipping: string | number | boolean;
}

const TRUE_VALUES = new Set(['1', 'true', 't', 'y', 'yes', '+', 'on', 'sep', 'noclip']);

function parseBoolean(val: string | number | boolean): boolean {
  const strVal = String(val).toLowerCase().trim();
  if (TRUE_VALUES.has(strVal)) return true;
  const FALSE_VALUES = new Set(['0', 'false', 'f', 'n', 'no', '-', 'off']);
  if (FALSE_VALUES.has(strVal)) return false;
  throw new Error(`Invalid boolean argument provided: ${val}. Must be true or false.`);
}

function ffprobeValue(inputFile: string, entry: string): string {
  return execSync(
    `ffprobe -v error -select_streams v:0 -show_entries stream=${entry} -of default=nw=1:nk=1 "${inputFile}"`,
    { encoding: 'utf-8' },
  ).trim();
}

function buildWaveFilter(
  {
    separateWaves,
    noPixelClipping,
    arg0 = 0,
    arg1 = 0,
    arg2 = 0,
    arg3 = 0,
    arg4 = 0,
    arg5 = 0,
    arg6 = 0,
    arg7 = 0,
  }: WaveFilterOptions,
  originalWidth: number,
  originalHeight: number,
): string {
  const isSeparate = parseBoolean(separateWaves);
  const isNoClipping = parseBoolean(noPixelClipping);

  const processingWidth = 640;
  const processingHeight = Math.round(((originalHeight / originalWidth) * processingWidth) / 2) * 2;

  const eqX = `X-((sin((T*5*${arg4}+(${arg7}*15))+(Y/H)*(PI*${arg5})))*(-15*${arg6}))`;
  const eqY = `Y-((sin((T*5*${arg0}+(${arg3}*15))+(X/W)*(PI*${arg1})))*(-15*${arg2}))`;

  let filterStr = '';
  if (isNoClipping) {
    filterStr += 'drawbox=t=1,';
  }
  filterStr += `format=yuv444p,scale=${processingWidth}:${processingHeight},`;
  if (isSeparate) {
    filterStr += `"geq='p(${eqX},Y)'","geq='p(X,${eqY})'",`;
  } else {
    filterStr += `"geq='p(${eqX},${eqY})'",`;
  }
  filterStr += `scale=${originalWidth}:${originalHeight},setsar=1:1,format=yuv420p`;
  return filterStr;
}

export function applyWaveFilter(opts: WaveFilterOptions): void {
  if (!fs.existsSync(opts.inputFile)) {
    throw new Error(`Input file not found: ${opts.inputFile}`);
  }

  const width = parseInt(ffprobeValue(opts.inputFile, 'width'), 10);
  const height = parseInt(ffprobeValue(opts.inputFile, 'height'), 10);
  if (Number.isNaN(width) || Number.isNaN(height)) {
    throw new Error('Could not determine video dimensions using ffprobe.');
  }

  const filterGraph = buildWaveFilter(opts, width, height);
  const outputDir = path.dirname(path.resolve(opts.outputFile));
  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }

  const ffmpegCmd = `ffmpeg -y -i "${opts.inputFile}" -vf ${filterGraph} -c:a copy "${opts.outputFile}"`;
  console.log(`\nExecuting FFmpeg Command:\n${ffmpegCmd}\n`);
  try {
    execSync(ffmpegCmd, { stdio: 'inherit' });
    console.log(`\nSuccess! Created: ${opts.outputFile}`);
  } catch (error) {
    console.error('\nError executing FFmpeg:', error);
    process.exit(1);
  }
}

// --- CLI Entrypoint ---
if (import.meta.url === pathToFileURL(process.argv[1]!).href) {
  const INPUT_VIDEO = 'input.mp4';
  const OUTPUT_VIDEO = './output/wave.mp4';

  const rawArgs = process.argv.slice(2);
  const [inputFile = INPUT_VIDEO, outputFile = OUTPUT_VIDEO, ...params] = rawArgs;

  const parseArg = (idx: number): number | undefined => {
    const val = params[idx];
    if (val === undefined) return undefined;
    const n = parseFloat(val);
    return Number.isNaN(n) ? undefined : n;
  };

  applyWaveFilter({
    inputFile,
    outputFile,
    arg0: parseArg(0),
    arg1: parseArg(1),
    arg2: parseArg(2),
    arg3: parseArg(3),
    arg4: parseArg(4),
    arg5: parseArg(5),
    arg6: parseArg(6),
    arg7: parseArg(7),
    separateWaves: params[8] ?? 'false',
    noPixelClipping: params[9] ?? 'false',
  });
}
