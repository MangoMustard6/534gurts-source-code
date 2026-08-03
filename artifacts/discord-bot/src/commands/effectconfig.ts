import { Message } from 'discord.js';

const PIPE_EFFECTS = [
  'hflip', 'vflip', 'invert', 'negate', 'grayscale', 'sepia', 'rotate',
  'ccshue', 'brightness', 'contrast', 'saturation', 'swapuv', 'mirror',
  'zoom', 'pinch&punch', 'p&p', 'pinchpunch', 'gm91deform', 'invertrgb', 'invlum',
  'volume', 'vibrato', 'areverse', 'vreverse', 'channelblend', 'huehsv',
  'multipitch', 'mp', 'multi', 'pitchtransition', 'pitchtrans', 'lut', 'syncaudio', 'speed', 'ffmpeg', 'frei0r', 'wave',
  'tvsim', 'tv', 'swirl', 'folkvalley', 'fv', 'labadjust', 'labadj', 'vocoder', 'ilvocodex',
  'orangevocoder', '4ormulator', 'audacity', 'magix', 'alimiter',
  'freakzinga', 'fzgm156', 'freakzingagm156', 'fgm156',
  'multipitch2', 'mp2', 'multipitch3', 'mp3', 'randomjitter', 'rj', 'trim', 'leftsplit',
  'rightsplit', 'ripple', 'scroll', 'pan', 'tile', 'watermark', 'ring',
  'miui', 'reddit', 'caption', 'orb', 'deorb', 'nepeta', 'gradientmap', 'gmap',
  'spherize', 'sphere', 'bulge', 'imagemagick', 'im', 'geq', 'wave2',
  'wmm3dripple', 'wmm', 'timecode', 'radar', 'freakzingatesteffect', 'fzte',
  'freaktest', 'stretch', 'scgv', 'sidechaingate_vocoder',
  'acontrast', 'adestroy', 'audioequalizer', 'avflip', 'nparisonffmpeg',
  'nineparisonffmpeg', '🥸🥸', '﷽', '𒐫', 'gm4', 'realgm4',
];

const EFFECT_ALIASES: Record<string, string> = {
  mp: 'multipitch',
  multi: 'multipitch',
  gm: 'gradientmap',
  gmap: 'gradientmap',
  rj: 'randomjitter',
  p2p: 'pinch&punch',
  pnp: 'pinch&punch',
};

const USAGE =
  '**Usage:** `th/effectconfig <effect>[=<param>[;param...]]`\n' +
  '**Also accepts:** spaces and commas as parameter separators.\n' +
  '**Examples:**\n' +
  '`th/effectconfig scgv carrier.mp3 64 2 0.5 peak` → `scgv=carrier.mp3;64;2;0.5;peak`\n' +
  '`th/effectconfig wave=1,15,0.8,0` → `wave=1;15;0.8;0`';

export function normalizeEffectConfig(raw: string): { ok: true; value: string } | { ok: false; error: string } {
  const tokens = raw.trim().split(/[=;,\s]+/).map((token) => token.trim()).filter(Boolean);
  if (!tokens.length) return { ok: false, error: 'No effect provided.' };

  const requested = tokens.shift()!.toLowerCase();
  const effect = EFFECT_ALIASES[requested] ?? requested;
  if (!PIPE_EFFECTS.includes(effect)) {
    return { ok: false, error: `Unknown pipe effect \`${requested}\`.` };
  }

  return {
    ok: true,
    value: tokens.length ? `${effect}=${tokens.join(';')}` : effect,
  };
}

export async function handleEffectConfig(message: Message, rest: string): Promise<void> {
  if (!rest.trim()) {
    await message.reply(
      `**Available pipe effects:**\n\`${PIPE_EFFECTS.join('`, `')}\`\n\n${USAGE}`,
    );
    return;
  }

  const result = normalizeEffectConfig(rest);
  if (!result.ok) {
    await message.reply(`❌ ${result.error}\n${USAGE}`);
    return;
  }

  await message.reply(`✅ **Normalized pipe configuration:**\n\`${result.value}\``);
}