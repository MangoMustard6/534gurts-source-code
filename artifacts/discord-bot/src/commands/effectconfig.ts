import { Message } from 'discord.js';
import { PIPE_EFFECT_NAMES } from '../effects.js';

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
  if (!PIPE_EFFECT_NAMES.has(effect)) {
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
      `**Available pipe effects:**\n\`${[...PIPE_EFFECT_NAMES].join('`, `')}\`\n\n${USAGE}`,
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