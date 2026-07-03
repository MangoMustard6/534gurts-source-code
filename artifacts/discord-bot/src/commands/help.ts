import { Message, EmbedBuilder, GuildPremiumTier } from 'discord.js';
import { getMaxRepetitions, getUploadLimitBytes, formatBytes } from '../utils/limits.js';
import { LIMITS, PREFIX } from '../config.js';

export async function handleHelp(message: Message, ownerId: string): Promise<void> {
  const guild = message.guild ?? null;
  const isOwner = ownerId !== '' && message.author.id === ownerId;
  const maxReps = getMaxRepetitions(message.author.id, ownerId, guild);
  const uploadLimit = getUploadLimitBytes(guild);
  const boosted = guild && guild.premiumTier >= GuildPremiumTier.Tier1;
  const boostBonus = boosted ? ` +${LIMITS.BOOST_BONUS}` : '';
  const baseReps = isOwner ? LIMITS.OWNER_MAX_REPS : LIMITS.NON_OWNER_MAX_REPS;

  const embeds: EmbedBuilder[] = [];

  // ── Page 1: Heavy Effects ─────────────────────────────────────────────────
  embeds.push(
    new EmbedBuilder()
      .setColor(0xe74c3c)
      .setAuthor({
        name: isOwner ? `👑 ${message.author.displayName}` : message.author.displayName,
        iconURL: message.author.displayAvatarURL(),
      })
      .setTitle('IHTX Bot — Commands  (1/3)')
      .setDescription(`Prefix: \`${PREFIX}\`  •  \`roxi \` for all commands`)
      .addFields(
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
            '`t!mirror <left|right|top|bottom|deg>` — Mirror media via FFmpeg split/flip/stack',
            '`t!huehsv <hue>` *hhsv* — Hue shift via ImageMagick haldclut',
            '`t!syncaudio [alt]` *sa sync* — Sync video/audio durations by adjusting speed',
          ].join('\n'),
        },
      )
      .setFooter({ text: 'Page 1/3 — IHTX Bot • FFmpeg, Rubber Band, yt-dlp' }),
  );

  // ── Page 2: TypeScript commands + Download + Info ─────────────────────────
  embeds.push(
    new EmbedBuilder()
      .setColor(0x5865f2)
      .setTitle('IHTX Bot — Commands  (2/3)')
      .addFields(
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
          name: '🎛️ TypeScript: t!realgmajor4',
          value: [
            `\`${PREFIX}realgmajor4\` *realgm4 rgm4* — RGB invert + pitch-shifted overlay + doubled volume`,
            `Attach or reply-to a video file. No additional arguments needed.`,
            `Uses rubberband for pitch shifting (+5 semitones) with consistency mode.`,
          ].join('\n'),
        },
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
      )
      .setFooter({ text: 'Page 2/3 — IHTX Bot' }),
  );

  // ── Page 3: Owner-only ────────────────────────────────────────────────────
  embeds.push(
    new EmbedBuilder()
      .setColor(0xf1c40f)
      .setTitle('IHTX Bot — Commands  (3/3) — 🔒 Owner Only')
      .addFields(
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
      )
      .setFooter({ text: 'Page 3/3 — IHTX Bot • Owner commands (Python bot)' }),
  );

  await message.reply({ embeds });
}
