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

  const footerText = `Page ${index + 1}/${total} — IHTX Bot ${TITLE_TAG}`;
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
    color: 0xe74c3c,
    title: `IHTX Bot — Commands ${TITLE_TAG}`,
    description: `Prefix: \`${PREFIX}\`  •  \`roxi \` for all commands`,
    fields: [
      {
        name: '🔥 Heavy Effects  *(slow/rate-limited)*',
        value: [
          '`t!ihtx [preset]` — Apply FFmpeg preset to attachment (chaos, glitch, melt, vhs, …)',
          '`t!ihtx <reps> <dur> <noTrim> <fmt> <effects>` — Custom pipe chain: `huehsv=0.5,negate,speed=1.5`',
          '`t!invlum [n]` *il* — Luma-inversion N times, all iterations concatenated',
          '`t!preview1280 [start] [dur]` *p1280 pv1280* — 12-segment TV-simulator montage',
          '`t!multipitch <semis>` *mp multi* — Multi-voice pitch shift (Rubber Band R3): `t!multipitch 25|5|8.5`',
          '`t!ffmpeg <args>` — Raw FFmpeg args on attachment: `t!ffmpeg -vf negate`',
          '`t!realgmajor4` *realgm4 rgm4* — RGB invert + pitch-shifted overlay + doubled volume',
          '`t!lexg` *lastexportgrab* — Re-apply last `t!ihtx` export to a new attachment',
        ].join('\n'),
      },
      {
        name: '🎞️ Pipe effects (comma-separated inside t!ihtx)',
        value: [
          '**Video:** `hflip` `vflip` `negate` `grayscale` `sepia` `rotate=<deg>` `huehsv=<val>` `swapuv` `invlum` `invertrgb=r;g;b` `gm91deform` `randomjitter=<strength>`',
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
          '`t!trim <start> <end>` — Trim audio/video/GIF (HH:MM:SS or seconds)',
          '`t!concatenate <url1> <url2> ... [fmt]` *concat* — Join 2-10 attachments/URLs into one file',
          '`t!join [media1] [media2] [-vertical]` — Join 2 videos side-by-side (default) or stacked',
          '`t!mirror <left|right|top|bottom|deg>` — Mirror media via FFmpeg split/flip/stack',
          '`t!huehsv <hue>` *hhsv* — Hue shift via ImageMagick haldclut',
          '`t!syncaudio [alt]` *sa sync* — Sync video/audio durations by adjusting speed',
        ].join('\n'),
      },
    ],
  });

  // ── Page 2: TypeScript commands + Download + Info ─────────────────────────
  pages.push({
    color: 0x5865f2,
    title: `IHTX Bot — Commands ${TITLE_TAG}`,
    fields: [
      {
        name: '⬇️ Download',
        value: [
          '`t!ytdl <url or search>` *youtubedownload* — Download video from URL or search query → Discord or catbox',
          '`t!ffmpegprocess <args>` *fmp* — FFmpeg on attachment with ffprobe metadata inspection (TypeScript bot)',
          '`t!catbox` *cb upload* — Upload attachment to catbox.moe (200 MB, permanent link)',
        ].join('\n'),
      },
      {
        name: '🎛️ TypeScript: t!multipitchihtx',
        value: [
          `\`pitches=0|-0.1|0.1\` — explicit semitone offsets, pipe-separated`,
          `\`repetitions=<n>\` — auto N evenly-spaced layers (default 20, max **${baseReps}${boostBonus}**)`,
          `\`spread=<n>\` — semitone range for auto mode (default 0.4)`,
          `\`duration=<sec>\` — stretch all layers to this length via rubberband --duration`,
          `\`engine=<r2|r3|r4>\` · \`window=<long|short>\``,
          `Example: \`${PREFIX}multipitchihtx repetitions=50 spread=1.5 engine=r3\``,
          `Example: \`${PREFIX}multipitchihtx pitches=-0.5|0|0.5 duration=30\``,
        ].join('\n'),
      },
      {
        name: '🎛️ TypeScript: t!multipitch2',
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
    color: 0x2ecc71,
    title: `IHTX Bot — Commands ${TITLE_TAG}`,
    fields: [
      {
        name: '🎮 Games  *(both bots)*',
        value: [
          '`t!coinflip` *flip coin cf* — Flip a coin',
          '`t!dice [expr]` *roll d* — Dice: `d20`, `2d6`, `3d8+5`',
          '`t!rps <rock|paper|scissors>` — Rock Paper Scissors vs bot',
          '`t!8ball <question>` *eightball* — Magic 8-Ball',
          '`t!slots` — Spin the slot machine',
          '`t!roulette <red|black|0-36>` — Roulette bet',
          '`t!choose <a | b | c>` *pick* — Pick a random option',
          '`t!trivia` — Random trivia (button answer, 30 s)',
          '`t!rate <thing>` — Rate something /10',
        ].join('\n'),
      },
      {
        name: '🤖 AI & Utility',
        value: [
          '`t!chat <prompt>` *ask* — Chat with Clankered (Gemini 2.5 Flash), both bots',
          '`t!clearchat` *resetai chatclear* — Clear your AI conversation history',
          '`t!random [sub]` *rand* — Random media from pool; `add`/`remove`/`list`/`clear` sub-commands',
          '`t!tag <name> [args]` *tags* — Custom scripting tags (variables, math, conditionals, iscript, IHTX)',
        ].join('\n'),
      },
      {
        name: 'ℹ️ Info',
        value: [
          '`t!help` — This embed',
          '`t!info` — Bot uptime, tool versions, your role',
          '`t!presets` *effects list* — List all IHTX presets',
          '`t!ihtxhelp [query]` *bothelp* — Full searchable Python bot help',
          '`t!updatelog` *updates changelog* — Recent bot updates',
          '`t!usage` *limit checklimit* — Check your heavy command usage',
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
    color: 0xf1c40f,
    title: `IHTX Bot — Commands ${TITLE_TAG} — 🔒 Owner Only`,
    fields: [
      {
        name: '🚫 Blocking',
        value: [
          '`t!blockuser` / `t!unblockuser <@user>` — Global user blocklist',
          '`t!blockchannel` / `t!unblockchannel` — Block channels from bot commands',
          '`t!keywordblock <kw> [#ch]` *kb* — Block a keyword (channel or global)',
          '`t!keywordblockremove <kw> [#ch]` *kbr* — Remove keyword block',
          '`t!keywordblockmsg <kw> <msg>` *kbmsg* — Custom reply for keyword block',
        ].join('\n'),
      },
      {
        name: '📣 Messaging',
        value: [
          '`t!say <msg>` — Bot sends a message',
          '`t!sayembed <content>` — Bot sends an embed',
          '`t!sendmsg <channelId> <msg>` *msgsend* — Send to any channel by ID',
        ].join('\n'),
      },
      {
        name: '🔄 Autoreplies',
        value: [
          '`t!autoreply <trigger> [#ch] <response>` *ar* — Add autoreply trigger',
          '`t!removeautoreply <trigger>` *rar deautoreply* — Remove autoreply',
          '`t!blockarchannel <trigger> [#ch]` *bac silencear* — Silence autoreply in channel',
          '`t!removearmentions <trigger>` *rarm* — Strip pings from autoreply',
          '`t!autoreplies` *arlist listautoreplies* — List all autoreplies',
          '`t!autoreply2` *ar2* — Toggle AI auto-reply for this channel',
          '`t!autoreply2list` *ar2list* — List AI auto-reply channels',
          '`t!removear2mentions <@user>` *rarm2* — Stop AI autoreply pinging a user',
        ].join('\n'),
      },
      {
        name: '⚠️ Moderation',
        value: [
          '`t!warn <@user> [reason]` — Warn a user',
          '`t!warnings <@user>` *warncount warnlist* — View user warnings',
          '`t!clearwarn <@user>` *unwarn clearwarnings* — Clear all warnings for user',
        ].join('\n'),
      },
      {
        name: '⚙️ Bot Admin',
        value: [
          '`t!setactivity <playing|watching|listening|streaming> <text>` *activity presence*',
          '`t!listservers` *servers guilds* — List all servers bot is in',
          '`t!listchannels <guildId>` *channels* — List channels in a server',
          '`t!resetlimit <@user>` *rl resetusage* — Reset a user\'s heavy command usage',
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
