import {
  Message,
  EmbedBuilder,
  GuildPremiumTier,
  ActionRowBuilder,
  ButtonBuilder,
  ButtonStyle,
  ComponentType,
} from 'discord.js';
import { getMaxRepetitions, getUploadLimitBytes, formatBytes } from '../utils/limits.js';
import { LIMITS, PREFIX } from '../config.js';

const TITLE_TAG = '(FULL COMMAND HELP)';
const PAGE_TIMEOUT_MS = 3 * 60_000;

// Discord embed limits, kept with a safety margin so we never hit a 400.
const FIELD_VALUE_LIMIT = 1000; // hard cap is 1024
const EMBED_TOTAL_BUDGET = 5500; // hard cap is 6000 across title+desc+fields+footer

interface HelpField {
  name: string;
  value: string;
}

interface HelpPage {
  color: number;
  title: string;
  description?: string;
  fields: HelpField[];
}

function truncate(text: string, max: number): string {
  if (text.length <= max) return text;
  return `${text.slice(0, max - 1).trimEnd()}…`;
}

/**
 * Truncates each field to FIELD_VALUE_LIMIT, then — if the embed is still over
 * budget once title/description/footer/field-names are counted — trims
 * further from the end of the longest fields until it fits. This keeps the
 * embed valid even if a page's content grows over time.
 */
function buildEmbed(page: HelpPage, index: number, total: number, author: Message['author']): EmbedBuilder {
  const fields = page.fields.map((f) => ({ name: f.name, value: truncate(f.value, FIELD_VALUE_LIMIT) }));

  const footerText = `Page ${index + 1}/${total} — 534gurts Bot ${TITLE_TAG}`;
  const fixedBudget =
    page.title.length + (page.description?.length ?? 0) + footerText.length +
    fields.reduce((sum, f) => sum + f.name.length, 0);
  let available = Math.max(0, EMBED_TOTAL_BUDGET - fixedBudget);

  for (const f of fields) {
    if (f.value.length <= available) {
      available -= f.value.length;
    } else {
      f.value = truncate(f.value, Math.max(0, available));
      available = 0;
    }
  }

  const embed = new EmbedBuilder()
    .setColor(page.color)
    .setTitle(page.title)
    .addFields(fields)
    .setFooter({ text: footerText });

  if (page.description) embed.setDescription(page.description);
  if (index === 0) {
    embed.setAuthor({
      name: author.displayName,
      iconURL: author.displayAvatarURL(),
    });
  }

  return embed;
}

function buildPages(message: Message, ownerId: string): HelpPage[] {
  const guild = message.guild ?? null;
  const isOwner = ownerId !== '' && message.author.id === ownerId;
  const maxReps = getMaxRepetitions(message.author.id, ownerId, guild);
  const uploadLimit = getUploadLimitBytes(guild);
  const boosted = guild && guild.premiumTier >= GuildPremiumTier.Tier1;
  const boostBonus = boosted ? ` +${LIMITS.BOOST_BONUS}` : '';
  const baseReps = isOwner ? LIMITS.OWNER_MAX_REPS : LIMITS.NON_OWNER_MAX_REPS;

  const pages: HelpPage[] = [];

  // ── Page 1: Heavy Effects ─────────────────────────────────────────────────
  pages.push({
    color: 0x40E0D0,
    title: `534gurts Bot — Commands ${TITLE_TAG}`,
    description: `Prefix: \`${PREFIX}\``,
    fields: [
      {
        name: '🔥 Heavy Effects  *(slow/rate-limited)*',
        value: [
          '`th/ihtx [preset]` — Apply FFmpeg preset to attachment (chaos, glitch, melt, vhs, …)',
          '`th/ihtx <reps> <dur> <noTrim> <fmt> <effects>` — Custom pipe chain: `huehsv=0.5,negate,speed=1.5`',
          '`th/invlum [n]` *il* — Luma-inversion N times, all iterations concatenated',
          '`th/preview1280 [start] [dur]` *p1280 pv1280* — 12-segment TV-simulator montage',
          '`th/multipitch <semis>` *mp multi* — Multi-voice pitch shift (Rubber Band R3): `th/multipitch 25|5|8.5`',
          '`th/multipitch_bungee [-7|7]` *mpb* — Bungee pitch-shifter, video passthrough, multi-pitch (e.g. `-7|7`; default `1.5`)',
          '`th/ffmpeg <args>` — Raw FFmpeg args on attachment: `th/ffmpeg -vf negate`',
          '`th/realgmajor4` *realgm4 rgm4* — RGB invert + pitch-shifted overlay + doubled volume',
          '`th/freakzingatesteffect` *fzte freaktest* — Full preset: invert + TV sim + wave + mirror + drawtext + mp3',
          '`th/lexg` *lastexportgrab* — Re-apply last `th/ihtx` export to a new attachment',
        ].join('\n'),
      },
      {
        name: '🎞️ Pipe effects (comma-separated inside th/ihtx)',
        value: [
          '**Video:** `hflip` `vflip` `negate` `grayscale` `sepia` `rotate=<deg>` `huehsv=<val>` `swapuv` `invlum` `invertrgb=r;g;b` `gm91deform` `randomjitter=<strength>` `gradientmap=<R,G,B[,A,pos]>...`',
          '**Color:** `ccshue=hue|sat|gamma|gain|offset`  `brightness=<v>` `contrast=<v>` `saturation=<v>`',
          '**Distortion:** `mirror=<deg|preset>` `zoom=<amt>` `ripple=spd|freq|amp|phase` `pan=px|py` `tile=tx|ty` `pinch&punch=str;r;cx;cy` `shake=<h>|<v>` `wave=hSpd|hFreq|hAmp|hPhase|vSpd|vFreq|vAmp|vPhase[|sep][|noclip]`',
          '**Scroll:** `scroll=hpos=V` · `scroll=h;v` · `scroll=x1:y1:x2:y2[:dur]` (animated pan)\n**Split:** `leftsplit(<inner>)` · `rightsplit(<inner>)` — apply inner effects to one half\n**Reverse:** `vreverse` (frames) · `areverse` (audio)',
          '**Audio:** `multipitch=semis` `volume=<val>` `vibrato=freq;depth` `syncaudio`',
          '**Overlay:** `nepeta[=url]` (cat-ear PNG or custom image scaled to video) `watermark=<url>` `ring[=url]` `miui` `reddit` `caption=<text>`',
          '**Plugins:** `frei0r=plugin:params` `lut=<url>` `speed=<factor>` `ffmpeg(<args>)`',
        ].join('\n'),
      },
      {
        name: '🎬 Video Tools',
        value: [
          '`th/trim <start> <end>` — Trim audio/video/GIF (HH:MM:SS or seconds)',
          '`th/concatenate <url1> <url2> ... [fmt]` *concat* — Join 2-10 attachments/URLs into one file',
          '`th/join [media1] [media2] [-vertical]` — Join 2 videos side-by-side (default) or stacked',
          '`th/mirror <left|right|top|bottom|deg>` — Mirror media via FFmpeg split/flip/stack',
          '`th/huehsv <hue>` *hhsv* — Hue shift via ImageMagick haldclut',
          '`th/gradientmap <R,G,B [A] [pos]> ...` *gm* — Gradient map via FFmpeg curves',
          '`th/syncaudio [alt]` *sa sync* — Sync video/audio durations by adjusting speed',
          '`th/pipetest <effect1;effect2;...>` *pt* — One-shot pipe effect runner',
        ].join('\n'),
      },
    ],
  });

  // ── Page 2: TypeScript commands + Download + Info ─────────────────────────
  pages.push({
    color: 0x40E0D0,
    title: `534gurts Bot — Commands ${TITLE_TAG}`,
    fields: [
      {
        name: '⬇️ Download',
        value: [
          '`th/ytdl <url or search>` *youtubedownload* — Download video from URL or search query → Discord or catbox',
          '`th/ffmpegprocess <args>` *fmp* — FFmpeg on attachment with ffprobe metadata inspection (TypeScript bot)',
          '`th/catbox` *cb upload* — Upload attachment to catbox.moe (200 MB, permanent link)',
        ].join('\n'),
      },
      {
        name: '🎨 TypeScript: th/gradientmap',
        value: [
          `\`${PREFIX}gradientmap <R,G,B [A] [pos]> ...\` *gm gmap* — apply a color gradient map via FFmpeg curves`,
          `**Examples:** \`${PREFIX}gradientmap 0,0,0 255,255,255\` · \`${PREFIX}gradientmap 0:0:0:255:0;255:0:0:255:0.5\``,
          `**Unlimited stops:** \`${PREFIX}gradientmap url:https://example.com/gradient.txt\` or attach a \`.txt\`/\`.csv\`/\`.json\` gradient file alongside the media.`,
        ].join('\n'),
      },
      {
        name: '🎛️ TypeScript: th/multipitch2',
        value: [
          `\`${PREFIX}multipitch2 <pitches> [||<wave-hammer>] [sr=<rate>]\` — attach a video/audio file`,
          `**Pitches:** pipe-separated integers, e.g. \`7|8|9\` or \`-3|0|4\``,
          `**Wave hammers:** \`G-Major_17\` (light limit) · \`Evil_Rampaging_Sorcerer\` (heavy limit)`,
          `**sr=N** — processing sample rate (default 44100)`,
          `Example: \`${PREFIX}multipitch2 7|8|9||G-Major_17\``,
          `Example: \`${PREFIX}multipitch2 -3|0|4||Evil_Rampaging_Sorcerer sr=48000\``,
        ].join('\n'),
      },
      {
        name: '🎛️ TypeScript: realgmajor4',
        value: `\`${PREFIX}realgmajor4\` *realgm4 rgm4* — Solarization curve + dual rubberband audio mix (×1.335) + vol×2. Attach or reply-to a video.`,
      },
      {
        name: '⏱️ TypeScript: stretch_to_length',
        value: [
          `\`${PREFIX}stretch_to_length <seconds>\` *stl* — Time-stretch media to hit an exact target duration (pitch preserved)`,
          `Attach, reply-to, or pass a media URL. Example: \`${PREFIX}stl 10\``,
        ].join('\n'),
      },
      {
        name: '🎵 TypeScript: ihtxsap  `/ihtxsap`',
        value: [
          `\`${PREFIX}ihtxsap <reps> <duration> <pitches> [style]\` *sap* — parallel pitch-layer processor, audio-only output (.mp3)`,
          `**Slash:** \`/ihtxsap file=<att> duration=<n> pitches=<s> [repetitions=<n>] [style=<s>]\``,
          `**Prefix pitches:** semicolon-separated semitones, e.g. \`-7;5;6\``,
          `**Slash pitches:** space-separated, e.g. \`-7 5 6\``,
          `**duration:** time-ratio multiplier (e.g. \`0.7\` = 70% speed)`,
          `**Styles:** \`Rubberband R2\` (default) · \`Rubberband R3\` · \`Soundtouch\` · \`Bungee\``,
          `**Example:** \`${PREFIX}ihtxsap 5 0.7 -7;5;6 "Rubberband R3"\``,
        ].join('\n'),
      },
    ],
  });

  // ── Page 3: Games + AI + Info ────────────────────────────────────────────
  pages.push({
    color: 0x40E0D0,
    title: `534gurts Bot — Commands ${TITLE_TAG}`,
    fields: [
      {
        name: '🎮 Games  *(both bots)*',
        value: [
          '`th/coinflip` *flip coin cf* — Flip a coin',
          '`th/dice [expr]` *roll d* — Dice: `d20`, `2d6`, `3d8+5`',
          '`th/rps <rock|paper|scissors>` — Rock Paper Scissors vs bot',
          '`th/8ball <question>` *eightball* — Magic 8-Ball',
          '`th/slots` — Spin the slot machine',
          '`th/roulette <red|black|0-36>` — Roulette bet',
          '`th/choose <a | b | c>` *pick* — Pick a random option',
          '`th/trivia` — Random trivia (button answer, 30 s)',
          '`th/rate <thing>` — Rate something /10',
        ].join('\n'),
      },
      {
        name: '🤖 AI & Utility',
        value: [
          '`th/chat <prompt>` *ask* — Chat with Clankered (Gemini 2.5 Flash), both bots',
          '`th/clearchat` *resetai chatclear* — Clear your AI conversation history',
          '`th/random [sub]` *rand* — Random media from pool; `add`/`remove`/`list`/`clear` sub-commands',
          '`th/tag <name> [args]` *tags* — Custom scripting tags (variables, math, conditionals, iscript, 534gurts)',
        ].join('\n'),
      },
      {
        name: 'ℹ️ Info',
        value: [
          '`th/help` — This embed',
          '`th/info` — Bot uptime, tool versions, your role',
          '`th/presets` *effects list* — List all 534gurts presets',
          '`th/ihtxhelp [query]` *bothelp* — Full searchable Python bot help',
          '`th/updatelog` *updates changelog* — Recent bot updates',
          '`th/usage` *limit checklimit* — Check your heavy command usage',
        ].join('\n'),
      },
      {
        name: '📊 Your Limits',
        value: [
          `Role: **${isOwner ? '👑 Owner' : 'User'}** · Boost: **${boosted ? `Tier ${guild!.premiumTier} ✅` : 'None'}**`,
          `Max repetitions: **${maxReps}** · Max upload: **${formatBytes(uploadLimit)}**`,
        ].join('\n'),
      },
    ],
  });

  // ── Page 4: Owner-only ────────────────────────────────────────────────────
  pages.push({
    color: 0x40E0D0,
    title: `534gurts Bot — Commands ${TITLE_TAG} — 🔒 Owner Only`,
    fields: [
      {
        name: '🚫 Blocking',
        value: [
          '`th/blockuser` / `th/unblockuser <@user>` — Global user blocklist',
          '`th/blockchannel` / `th/unblockchannel` — Block users from bot commands in this channel',
          '`th/keywordblock <kw> [#ch]` *kb* — Block a keyword (channel or global)',
          '`th/keywordblockremove <kw> [#ch]` *kbr* — Remove keyword block',
          '`th/keywordblockmsg <kw> <msg>` *kbmsg* — Custom reply for keyword block',
        ].join('\n'),
      },
      {
        name: '📣 Messaging',
        value: [
          '`th/say <msg>` — Bot sends a message',
          '`th/sayembed <content>` — Bot sends an embed',
          '`th/sendmsg <channelId> <msg>` *msgsend* — Send to any channel by ID',
        ].join('\n'),
      },
      {
        name: '🔄 Autoreplies',
        value: [
          '`th/autoreply <trigger> [#ch] <response>` *ar* — Add autoreply trigger',
          '`th/removeautoreply <trigger>` *rar deautoreply* — Remove autoreply',
          '`th/blockarchannel <trigger> [#ch]` *bac silencear* — Silence autoreply in channel',
          '`th/removearmentions <trigger>` *rarm* — Strip pings from autoreply',
          '`th/autoreplies` *arlist listautoreplies* — List all autoreplies',
          '`th/autoreply2` *ar2* — Toggle AI auto-reply for this channel',
          '`th/autoreply2list` *ar2list* — List AI auto-reply channels',
          '`th/removear2mentions <@user>` *rarm2* — Stop AI autoreply pinging a user',
        ].join('\n'),
      },
      {
        name: '⚠️ Moderation',
        value: [
          '`th/warn <@user> [reason]` — Warn a user',
          '`th/warnings <@user>` *warncount warnlist* — View user warnings',
          '`th/clearwarn <@user>` *unwarn clearwarnings* — Clear all warnings for user',
        ].join('\n'),
      },
      {
        name: '⚙️ Bot Admin',
        value: [
          '`th/setactivity <playing|watching|listening|streaming> <text>` *activity presence*',
          '`th/listservers` *servers guilds* — List all servers bot is in',
          '`th/listchannels <guildId>` *channels* — List channels in a server',
          '`th/resetlimit <@user>` *rl resetusage* — Reset a user\'s heavy command usage',
        ].join('\n'),
      },
    ],
  });

  return pages;
}

function buildRow(index: number, total: number, disabled: boolean): ActionRowBuilder<ButtonBuilder> {
  return new ActionRowBuilder<ButtonBuilder>().addComponents(
    new ButtonBuilder()
      .setCustomId('help_prev')
      .setEmoji('◀️')
      .setStyle(ButtonStyle.Secondary)
      .setDisabled(disabled || index === 0),
    new ButtonBuilder()
      .setCustomId('help_page')
      .setLabel(`${index + 1} / ${total}`)
      .setStyle(ButtonStyle.Secondary)
      .setDisabled(true),
    new ButtonBuilder()
      .setCustomId('help_next')
      .setEmoji('▶️')
      .setStyle(ButtonStyle.Secondary)
      .setDisabled(disabled || index === total - 1),
  );
}

export async function handleHelp(message: Message, ownerId: string): Promise<void> {
  const pages = buildPages(message, ownerId);
  let index = 0;

  const embed = buildEmbed(pages[index], index, pages.length, message.author);
  const row = buildRow(index, pages.length, false);

  const reply = await message.reply({ embeds: [embed], components: pages.length > 1 ? [row] : [] });

  if (pages.length <= 1) return;

  const collector = reply.createMessageComponentCollector({
    componentType: ComponentType.Button,
    time: PAGE_TIMEOUT_MS,
  });

  collector.on('collect', async (btn) => {
    if (btn.customId === 'help_prev') index = Math.max(0, index - 1);
    else if (btn.customId === 'help_next') index = Math.min(pages.length - 1, index + 1);

    const nextEmbed = buildEmbed(pages[index], index, pages.length, message.author);
    const nextRow = buildRow(index, pages.length, false);
    await btn.update({ embeds: [nextEmbed], components: [nextRow] });
  });

  collector.on('end', async () => {
    const finalRow = buildRow(index, pages.length, true);
    await reply.edit({ components: [finalRow] }).catch(() => {});
  });
}
