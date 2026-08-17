export interface VocoderArgs {
  /** arg 0: Whether to return/show the generated command code */
  showCode?: boolean;
  /** arg 1: Input URL / file path for the audio source */
  url: string;
  /** arg 2: Number of frequency bands / bandwidth split (default: 64) */
  bandwidth?: number;
  /** arg 3: Detection mode (default: 'peak') */
  detection?: string;
  /** arg 4: Release time (default: 50) */
  release?: number;
  /** arg 5: Attack time (default: 0.01) */
  attack?: number;
  /** arg 6: Gate ratio (default: 2) */
  ratio?: number;
  /** arg 7: Gate threshold (default: 1) */
  threshold?: number;
  /** arg 8: Makeup gain (default: 1) */
  makeup?: number;
  /** arg 9: Knee value (default: 8) */
  knee?: number;
  /** arg 10: Pitch shift factor in semitones (default: 0) */
  pitch?: number;
  /** arg 11: Gate range (default: 0) */
  range?: number;
  /** arg 12: Limiter volume level (default: 1) */
  volume?: number;
}

export interface VocoderResult {
  usageHelp?: string;
  ffmpegArgs?: string[];
  commandString?: string;
}

/**
 * Builds the FFmpeg sidechain-gate vocoder command based on positional arguments.
 */
export function buildVocoderCommand(args: Partial<VocoderArgs> & { url?: string }): VocoderResult {
  if (!args.url || args.url.trim() === '') {
    return {
      usageHelp:
        'Usage: .t <tagname> <show_code> <url> <bandwidth> <detection> <release> <attack> <ratio> <threshold> <makeup> <knee> <pitch> <range> <volume>',
    };
  }

  const showCode = args.showCode ?? false;
  const url = args.url;
  const bands = Math.max(1, Math.min(256, Math.floor(args.bandwidth ?? 64)));
  const rawDetection = String(args.detection ?? 'peak').trim().toLowerCase();
  const detection = rawDetection === '0' ? 'peak' : rawDetection === '1' ? 'rms' : rawDetection;
  const release = args.release ?? 50;
  const attack = args.attack ?? 0.01;
  const ratio = args.ratio ?? 2;
  const threshold = args.threshold ?? 1;
  const makeup = args.makeup ?? 1;
  const knee = args.knee ?? 8;
  const pitch = args.pitch ?? 0;
  const range = args.range ?? 0;
  const volume = args.volume ?? 1;

  if (!['peak', 'rms'].includes(detection)) {
    return {
      usageHelp: 'scgv detection must be `peak` or `rms` (numeric aliases: 0 or 1).',
    };
  }
  if (threshold < 0 || threshold > 1) {
    return { usageHelp: 'scgv threshold must be between 0 and 1.' };
  }
  if (range < 0 || range > 1) {
    return { usageHelp: 'scgv range must be between 0 and 1.' };
  }
  if (ratio < 1 || ratio > 9000) {
    return { usageHelp: 'scgv ratio must be between 1 and 9000.' };
  }
  if (attack < 0.01 || release < 0.01) {
    return { usageHelp: 'scgv attack and release must be at least 0.01.' };
  }
  if (makeup < 1 || makeup > 64) {
    return { usageHelp: 'scgv makeup must be between 1 and 64.' };
  }
  if (knee < 1 || knee > 8) {
    return { usageHelp: 'scgv knee must be between 1 and 8.' };
  }

  const pitchFilter =
    pitch !== 0 ? `rubberband=pitch=2^(${pitch}/12):phase=2.14748e+09/3:window=short,` : '';

  const modLabelSplit = Array.from({ length: bands }, (_, i) => `[mod${i + 1}]`).join('');
  const carrLabelSplit = Array.from({ length: bands }, (_, i) => `[carr${i + 1}]`).join('');

  let filterComplex = `[0]aformat=cl=mono,${pitchFilter}asplit=${bands}${modLabelSplit};`;
  filterComplex += `[1]aformat=cl=mono,asplit=${bands}${carrLabelSplit};`;

  for (let i = 1; i <= bands; i++) {
    const lowFreq = (i - 1) * (20000 / bands);
    const highFreq = i * (20000 / bands);
    filterComplex +=
      `[mod${i}]firequalizer=gain='if(between(f,${lowFreq},${highFreq}), 0, -INF)':accuracy=100:fixed=1:wfunc=nuttall,atrim=0.01[m${i}];`;
  }

  for (let i = 1; i <= bands; i++) {
    const lowFreq = (i - 1) * (20000 / bands);
    const highFreq = i * (20000 / bands);
    filterComplex +=
      `[carr${i}]firequalizer=gain='if(between(f,${lowFreq},${highFreq}), 0, -INF)':accuracy=100:fixed=1:wfunc=nuttall,atrim=0.01[c${i}];`;
  }

  for (let i = 1; i <= bands; i++) {
    filterComplex +=
      `[c${i}][m${i}]sidechaingate=ratio=${ratio}:threshold=${threshold}:range=${range}:attack=${attack}:release=${release}:makeup=${makeup}:knee=${knee}:detection=${detection}:level_sc=sqrt(${bands})[v${i}];`;
  }

  const mixedLabels = Array.from({ length: bands }, (_, i) => `[v${i + 1}]`).join('');
  filterComplex += `${mixedLabels}amix=${bands}:normalize=0,crystalizer,alimiter=${volume}:latency=1[a]`;

  const ffmpegArgs = [
    '-stream_loop',
    '-1',
    '-i',
    url,
    '-filter_complex',
    filterComplex,
    '-map',
    '0:v',
    '-map',
    '[a]',
  ];

  const fullCommand = `ffmpeg -i $FILE_1 ${ffmpegArgs.join(' ')} ./output/sidechaingate_vocoder.mp4`;

  return {
    ffmpegArgs,
    commandString: showCode ? fullCommand : undefined,
  };
}