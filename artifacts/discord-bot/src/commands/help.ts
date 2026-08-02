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
    color: 0x40E0D0,
    title: `IHTX Bot — Commands ${TITLE_TAG}`,
    description: `Prefix: \`${PREFIX}\``,
    fields: [
      {
        name: '🔥 Heavy Effects  *(rate-limited)*',
        value: [
          '`th/ihtx [preset]` — Apply FFmpeg preset (chaos, glitch, melt, vhs, …)',
          '`th/ihtx <reps> <dur> <noTrim> <fmt> <effects>` — Custom pipe chain: `huehsv=0.5,negate,speed=1.5`',
          '`th/invlum [n]` *il* — Luma-inversion N times, all iterations concatenated',
          '`th/multipitch_bungee [-7|7]` *mpb* — Bungee pitch-shifter + video passthrough (heavy)',
          '`th/concatenate <url1> <url2> ... [fmt]` *concat* — Join 2-10 attachments/URLs',
          '`th/join [media1] [media2] [-vertical]` — Join 2 videos side-by-side or stacked',
          '`th/ffmpeg <args>` — Raw FFmpeg args on attachment: `th/ffmpeg -vf negate`',
          '`th/realgmajor4` *realgm4 rgm4* — RGB invert + pitch-shifted overlay + vol×2',
          '`th/freakzingatesteffect` *fzte freaktest* — Full preset: invert+TVsim+wave+mirror+mp3',
          '`th/ihtxsap <reps> <dur> <pitches> [style]` *sap* — iterative pitch-layer processor',
        ].join('\n'),
      },
      {
        name: '🎞️ Pipe effects (comma-separated in th/ihtx)',
        value: [
          '**Video:** `hflip` `vflip` `negate` `grayscale` `sepia` `rotate=<deg>` `huehsv=h|sat|lum` `swapuv` `invlum` `invertrgb=r;g;b` `gm91deform` `randomjitter=<str>` `gradientmap=<R,G,B[,A,pos]>...`',
          '**Color:** `ccshue=hue|sat|gamma|gain|offset` `brightness=<v>` `contrast=<v>` `saturation=<v>` `labadjust=l;a;b`',
          '**Distortion:** `mirror=<deg|L/R/T/B>` `zoom=<amt>` `ripple=spd|freq|amp|phase` `pan=px|py` `tile=tx|ty` `pinch&punch=str;r;cx;cy` `shake=h|v` `spherize=amt|r|cx|cy` `swirl=str[;r;xc;yc]`',
          '**Wave:** `wave=hSpd|hFreq|hAmp|hPhase|vSpd|vFreq|vAmp|vPhase[|sep][|noclip]` — presets: `largeWave` `mediumWave` `smallWave` `horizontalOnly` `verticalOnly`',
          '**Scroll/Split/Reverse:** `scroll=hpos=V` · `scroll=h;v` · `scroll=x1:y1:x2:y2[:dur]` · `leftsplit(<fx>)` · `rightsplit(<fx>)` · `vreverse` · `areverse`',
          '**Audio:** `multipitch=semis` `volume=<val>` `vibrato=freq;depth` `syncaudio` `vocoder=mode;url` `scgv=carrier_url[;bands;ratio;threshold;release;attack;makeup;knee;detection;range;volume;pitch]` `tvsim=curvature[;…]`',
          '**Overlay/FX:** `nepeta[=url]` `watermark=<url>` `ring[=url]` `miui` `reddit` `caption=<text>` `folkvalley`/`fv` `frei0r=plugin:p` `lut=<url>` `speed=<x>` `ffmpeg(<args>)`',
        ].join('\n'),
      },
      {
        name: '🎬 Video Tools  *(not rate-limited)*',
        value: [
          '`th/multipitch <semis>` *mp multi* — Multi-voice pitch shift (Rubber Band R3)',
          '`th/preview1280 [start] [dur]` *p1280* — 12-segment TV-simulator montage',
          '`th/oppositep1280 [start] [dur]` *op1280* — Inverse TV-simulator montage',
          '`th/preview1280with640x360resize` *p1280ff!3* — preview1280 locked to 640×360',
          '`th/preview1280what [s] [dur] [len] [tempo]` *p1280what p1280fev8v2plus* — **28-segment** extended montage (v8 v2+); pass `true` for tempo-stretch',
          '`th/tvsim <curvature> [...]` *tv* — CRT/TV simulator (displacement map)',
          '`th/swirl <strength> [...]` *vortex* — Vortex/swirl distortion via geq',
          '`th/folkvalley` *fv folk* — Music swap + brightness boost + overlay',
          '`th/vocoder [mode] <carrier_url>` *vocode* — FFT phase vocoder',
          '`th/scgv <carrier_url> [bandwidth] [...]` *sidechaingate_vocoder* — Sidechain-gate vocoder',
          '`th/trim <start> <end>` · `th/repeat [n]` *rep* · `th/mirror <side>` · `th/huehsv <hue>` *hhsv* · `th/syncaudio` *sa* · `th/pipetest <fx>` *pt* · `th/lexg` *lec*',
          '`th/download <url>` *dl* — Download any media URL; `th/videolength <url>` *vidlen* — Get duration',
        ].join('\n'),
      },
    ],
  });

  // ── Page 2: TypeScript commands ───────────────────────────────────────────
  pages.push({
    color: 0x40E0D0,
    title: `IHTX Bot — Commands ${TITLE_TAG}`,
    fields: [
      {
        name: '⬇️ Download & Media',
        value: [
          '`th/ytdl <url or search>` *youtubedownload* — Download video from URL/search → Discord or catbox',
          '`th/download <url>` *dl* — Download any media URL incl. Discord CDN links (Python bot)',
          '`th/videolength <url>` *vidlen videolen* — FFprobe a URL, returns H:MM:SS duration (TS bot)',
          '`th/ffmpegprocess <args>` *fmp* — FFmpeg on attachment with ffprobe metadata (TS bot)',
          '`th/catbox` *cb upload* — Upload attachment to catbox.moe (uguu.se fallback)',
          '`th/uguu` *ugupload* — Upload attachment directly to uguu.se',
          '`th/bytebeat <expr> [sr]` — Generate audio from a bytebeat math expression (TS bot)',
        ].join('\n'),
      },
      {
        name: '🎨 TypeScript: th/gradientmap / th/wave',
        value: [
          `\`${PREFIX}gradientmap <R,G,B [A] [pos]> ...\` *gm gmap* — Color gradient map via FFmpeg curves`,
          `**Examples:** \`${PREFIX}gm 0,0,0 255,255,255\` · \`${PREFIX}gm url:https://example.com/grad.txt\``,
          `\`${PREFIX}wave <preset>\` — Standalone wave: \`largeWave\` \`mediumWave\` \`smallWave\` \`horizontalOnly\` \`verticalOnly\``,
        ].join('\n'),
      },
      {
        name: '🎛️ TypeScript: th/multipitch2',
        value: [
          `\`${PREFIX}multipitch2 <pitches> [||<wave-hammer>] [sr=<rate>]\` — attach a video/audio file`,
          `**Pitches:** pipe-separated integers e.g. \`7|8|9\` or \`-3|0|4\``,
          `**Wave hammers:** \`G-Major_17\` (light) · \`Evil_Rampaging_Sorcerer\` (heavy)`,
          `Example: \`${PREFIX}multipitch2 7|8|9||G-Major_17\``,
        ].join('\n'),
      },
      {
        name: '🎛️ TypeScript: realgmajor4 / stretch_to_length',
        value: [
          `\`${PREFIX}realgmajor4\` *realgm4 rgm4* — Solarization curve + dual rubberband audio mix (×1.335) + vol×2`,
          `\`${PREFIX}stretch_to_length <seconds>\` *stl* — Time-stretch media to exact duration (pitch preserved)`,
        ].join('\n'),
      },
      {
        name: '🎵 TypeScript: ihtxsap  `/ihtxsap`',
        value: [
          `\`${PREFIX}ihtxsap <reps> <duration> <pitches> [style]\` *sap* — parallel pitch-layer processor`,
          `**Slash:** \`/ihtxsap file=<att> duration=<n> pitches=<s> [repetitions=<n>] [style=<s>]\``,
          `**Pitches:** \`;-7;5;6\` (prefix) · \`-7 5 6\` (slash) · **duration:** time-ratio (0.7 = 70% speed)`,
          `**Styles:** \`Rubberband R2\` · \`Rubberband R3\` · \`Soundtouch\` · \`Bungee\` · \`Rubberband Custom\``,
        ].join('\n'),
      },
    ],
  });

  // ── Page 3: Games + AI + Info ─────────────────────────────────────────────
  pages.push({
    color: 0x40E0D0,
    title: `IHTX Bot — Commands ${TITLE_TAG}`,
    fields: [
      {
        name: '🎮 Games  *(TypeScript bot)*',
        value: [
          '`th/coinflip` *flip coin cf* — Flip a coin',
          '`th/dice [expr]` *roll d* — Dice rolls: `d20`, `2d6`, `3d8+5`',
          '`th/rps <rock|paper|scissors>` — Rock Paper Scissors vs bot',
          '`th/8ball <question>` *eightball* — Magic 8-Ball',
          '`th/slots` — Spin the slot machine 🎰',
          '`th/roulette <red|black|0-36>` — Roulette bet',
          '`th/choose <a | b | c>` *pick* — Pick a random option from a list',
          '`th/trivia` — Random trivia (button answer, 30 s)',
        ].join('\n'),
      },
      {
        name: '🎮 Games  *(Python bot)*',
        value: [
          '`th/rate <thing>` — Rate something /10 (deterministic)',
          '`th/numguess` *ng guess* — Guess a number 1–100, 7 tries, 30 s each',
          '`th/scramble` *ws wordscramble* — Unscramble a video/audio-related word, 30 s',
          '`th/typerace` *tr type typer* — Race to type a phrase, reports WPM, 60 s',
          '`th/mathquiz` *mq* — 5 arithmetic questions, 10 s each',
        ].join('\n'),
      },
      {
        name: '🤖 AI & Utility',
        value: [
          '`th/chat <prompt>` *ask* — Chat with Clankered (Groq), both bots',
          '`th/clearchat` *resetai chatclear* — Clear your AI conversation history',
          '`th/random [sub]` *rand* — Random media from pool; `add`/`remove`/`list`/`clear`',
          '`th/tag <name> [args]` *tags* — Custom scripting tags (variables, math, iscript, IHTX)',
          '`th/submiteffect <name> <effects>` *se addeffect* — Submit named pipe-effect combo',
          '`th/listeffects` *le effectlist* — Browse user-submitted effects (paginated)',
          '`th/effectconfig <effect> <params>` *ec* — Normalize pipe-effect settings into `effect=param;param` configuration',
        ].join('\n'),
      },
      {
        name: 'ℹ️ Info & Limits',
        value: [
          '`th/help` — This embed  ·  `th/ihtxhelp [query]` *bothelp* — Full Python bot help',
          '`th/info` — Uptime, tool versions, your role',
          '`th/presets` *effects list* — List all IHTX presets',
          '`th/updatelog` *updates changelog* — Recent bot updates',
          '`th/usage` *limit checklimit* — Check your heavy command usage',
          '`th/invite` — Bot invite link',
          `Role: **${isOwner ? '👑 Owner' : 'User'}** · Boost: **${boosted ? `Tier ${guild!.premiumTier} ✅` : 'None'}** · Reps: **${maxReps}** · Upload: **${formatBytes(uploadLimit)}**`,
        ].join('\n'),
      },
    ],
  });

  // ── Page 4: Owner-only ────────────────────────────────────────────────────
  pages.push({
    color: 0x40E0D0,
    title: `IHTX Bot — Commands ${TITLE_TAG} — 🔒 Owner Only`,
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
