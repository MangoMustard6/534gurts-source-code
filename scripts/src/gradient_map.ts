import { execSync } from 'node:child_process';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { pathToFileURL } from 'node:url';

// Define a type for a color stop: [R, G, B, Alpha?, Position?]
export type ColorStop = [number, number, number, number?, number?];

export interface GradientMapOptions {
  inputFile: string;
  outputFile: string;
  colors: ColorStop[];
}

/**
 * Generates an FFmpeg gradient map filter from an array of colors and applies it to a video.
 */
export function applyGradientMap({ inputFile, outputFile, colors }: GradientMapOptions): void {
  if (!fs.existsSync(inputFile)) {
    throw new Error(`Input file not found: ${inputFile}`);
  }

  if (colors.length === 0) {
    throw new Error('You must provide at least one color stop.');
  }

  // Normalize the colors array to ensure Alpha and Position exist for mapping.
  // If Position is missing, distribute color points evenly between 0 and 1.
  const normalizedColors = colors.map((c, i) => {
    const r = c[0];
    const g = c[1];
    const b = c[2];
    const a = c[3] !== undefined ? c[3] : 255; // Default Alpha to 255 (opaque)
    const pos = c[4] !== undefined ? c[4] : i / Math.max(colors.length - 1, 1);

    return { r, g, b, a, pos };
  });

  // Generate the curve points (FFmpeg format: "position/intensity position/intensity ...")
  const rCurve = normalizedColors.map((c) => `${c.pos}/${c.r / 255}`).join(' ');
  const gCurve = normalizedColors.map((c) => `${c.pos}/${c.g / 255}`).join(' ');
  const bCurve = normalizedColors.map((c) => `${c.pos}/${c.b / 255}`).join(' ');
  const aCurve = normalizedColors.map((c) => `${c.pos}/${c.a / 255}`).join(' ');

  // Construct the complex filtergraph string
  const vfString =
    `split=3[a][b][t];` +
    `[a]format=gray,curves=r='${rCurve}':g='${gCurve}':b='${bCurve}'[aa];` +
    `[b]format=gray,curves=all='${aCurve}'[bb];` +
    `[aa][bb]alphamerge[c];` +
    `[t][c]overlay,format=yuv420p[v]`;

  // Ensure the output directory exists
  const outputDir = path.dirname(path.resolve(outputFile));
  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }

  // Build the FFmpeg command
  const ffmpegCmd = `ffmpeg -y -i "${inputFile}" -filter_complex "${vfString}" -map "[v]" -pix_fmt yuv420p "${outputFile}"`;

  console.log(`\nExecuting FFmpeg Command:\n${ffmpegCmd}\n`);

  // Run the command and pipe FFmpeg output straight to the console
  try {
    execSync(ffmpegCmd, { stdio: 'inherit' });
    console.log(`\nSuccess! Created: ${outputFile}`);
  } catch (error) {
    console.error('\nError executing FFmpeg:', error);
    process.exit(1);
  }
}

// --- CLI Entrypoint ---
if (import.meta.url === pathToFileURL(process.argv[1]!).href) {
  const INPUT_VIDEO = 'input.mp4';
  const OUTPUT_VIDEO = './output/gradient_map.mp4';

  // Snag everything after "tsx gradient_map.ts"
  const rawArgs = process.argv.slice(2);

  if (rawArgs.length === 0) {
    console.log('=========================================================================');
    console.log('FFmpeg Unlimited Gradient Map Generator');
    console.log('=========================================================================');
    console.log('Usage: tsx gradient_map.ts <Color1> <Color2> ... <ColorN>');
    console.log('Format: R,G,B[,Alpha,Position]');
    console.log('\nExamples:');
    console.log('  1. Simple Black-to-Orange-to-White gradient:');
    console.log('     tsx gradient_map.ts 0,0,0 255,128,0 255,255,255');
    console.log('\n  2. Custom position and transparency (Position is 0 to 1):');
    console.log('     tsx gradient_map.ts 0,0,0,255,0 0,0,255,128,0.3 255,255,255,255,1');
    console.log('=========================================================================');
    process.exit(0);
  }

  try {
    // Map the CLI arguments dynamically
    const colorArgs: ColorStop[] = rawArgs.map((arg, idx) => {
      const parts = arg.split(',').map(Number);

      if (parts.length < 3 || parts.some(isNaN)) {
        throw new Error(
          `Invalid color block at index ${idx}: "${arg}". Must be formatted as R,G,B[,A,Pos] using numbers.`,
        );
      }

      return [
        parts[0], // R
        parts[1], // G
        parts[2], // B
        parts[3], // A (Optional)
        parts[4], // Pos (Optional)
      ] as ColorStop;
    });

    console.log(`Loaded ${colorArgs.length} color points. Mapping gradient...`);

    applyGradientMap({
      inputFile: INPUT_VIDEO,
      outputFile: OUTPUT_VIDEO,
      colors: colorArgs,
    });
  } catch (err: any) {
    console.error(`\nError: ${err.message}`);
    process.exit(1);
  }
}
