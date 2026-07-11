import {
  Client,
  GatewayIntentBits,
  Partials,
  Message,
  REST,
  Routes,
  Interaction,
  ChatInputCommandInteraction,
  SlashCommandBuilder,
} from 'discord.js';
import { BOT_TOKEN, BOT_OWNER_ID, PREFIX } from './config.js';
import { runYtdl } from './commands/ytdl.js';
import { handleMultipitchIHTX } from './commands/multipitchihtx.js';
import { handleHelp } from './commands/help.js';
import { handleCoinflip } from './commands/games/coinflip.js';
import { handleDice } from './commands/games/dice.js';
import { handleRPS } from './commands/games/rps.js';
import { handleEightBall } from './commands/games/eightball.js';
import { handleSlots } from './commands/games/slots.js';
import { handleChoose } from './commands/games/choose.js';
import { handleRoulette } from './commands/games/roulette.js';
import { handleTrivia } from './commands/games/trivia.js';
import { handleInfo } from './commands/info.js';
import { handleCatbox } from './commands/catbox.js';
import { handleChat } from './commands/chat.js';
import { handleClearchat } from './commands/clearchat.js';
import { handleBytebeat, handleBytebeatInteraction } from './commands/bytebeat.js';
import { handleFfmpegProcess } from './commands/ffmpegprocess.js';
import { handleRealGMajor4 } from './commands/realgmajor4.js';
import { handleMultipitch2 } from './commands/multipitch2.js';
import { handleIhtxSap, handleIhtxSapInteraction, IHTXSAP_STYLE_CHOICES } from './commands/ihtxsap.js';
import { handleStretchToLength } from './commands/stretchtolength.js';

if (!BOT_TOKEN) {
  console.error('ERROR: DISCORD_TOKEN environment variable is not set.');
  process.exit(1);
}

// ── Slash command definitions ────────────────────────────────────────────────

const SLASH_COMMANDS = [
  new SlashCommandBuilder()
    .setName('bytebeat')
    .setDescription('Generate Bytebeat audio from a mathematical formula')
    .addStringOption((opt) =>
      opt
        .setName('formula')
        .setDescription('Formula using t (sample index 0–39 999), e.g. t*(t>>5|t>>8)')
        .setRequired(true),
    )
    .toJSON(),

  new SlashCommandBuilder()
    .setName('ihtxsap')
    .setDescription('IHTX-Sap: pitch-layer audio processor — strips video, outputs pure MP3')
    .addAttachmentOption((opt) =>
      opt.setName('file').setDescription('Audio or video file to process (images rejected)').setRequired(true),
    )
    .addNumberOption((opt) =>
      opt.setName('duration').setDescription('How many seconds of the input to use, e.g. 0.7 = first 0.7 s').setRequired(true),
    )
    .addStringOption((opt) =>
      opt.setName('pitches').setDescription('Space-separated semitone shifts, e.g. "-7 5 6"').setRequired(true),
    )
    .addIntegerOption((opt) =>
      opt.setName('repetitions').setDescription('Times the mix loops end-to-end (default: 5, max: 100)').setRequired(false),
    )
    .addStringOption((opt) =>
      opt
        .setName('style')
        .setDescription('Processing engine (default: Rubberband R2)')
        .setRequired(false)
        .addChoices(...IHTXSAP_STYLE_CHOICES.map((c) => ({ name: c.name, value: c.value }))),
    )
    .addNumberOption((opt) =>
      opt.setName('volume').setDescription('Output volume multiplier after mix, e.g. 8 (default: 1)').setRequired(false),
    )
    .toJSON(),
];

// ── Discord client ───────────────────────────────────────────────────────────

const client = new Client({
  intents: [
    GatewayIntentBits.Guilds,
    GatewayIntentBits.GuildMessages,
    GatewayIntentBits.MessageContent,
    GatewayIntentBits.DirectMessages,
  ],
  partials: [Partials.Channel],
});

// ── Ready: log in + register slash commands ──────────────────────────────────

client.once('clientReady', async (c) => {
  console.log(`[IHTX-TS] Logged in as ${c.user.tag}`);
  console.log(`[IHTX-TS] Prefix: ${PREFIX}`);
  console.log(`[IHTX-TS] Owner ID: ${BOT_OWNER_ID || '(not set)'}`);
  console.log(`[IHTX-TS] Commands: ytdl, youtubedownload, multipitchihtx, multipitch2, ihtxsap, chat, ask, clearchat, coinflip, dice, rps, 8ball, slots, choose, roulette, trivia, help, info, catbox, bytebeat, ffmpegprocess, realgmajor4, stretch_to_length`);

  // Register slash commands.
  // Set BOT_GUILD_ID env var for instant guild-level registration (dev),
  // or leave unset for global registration (up to 1 h propagation).
  const guildId = process.env.BOT_GUILD_ID ?? '';

  try {
    const rest = new REST({ version: '10' }).setToken(BOT_TOKEN);
    // Read-only fields Discord rejects if sent back on a bulk PUT.
    const RO_KEYS = new Set(['application_id', 'version']);

    if (guildId) {
      await rest.put(Routes.applicationGuildCommands(c.user.id, guildId), {
        body: SLASH_COMMANDS,
      });
      console.log(`[IHTX-TS] Slash commands registered to guild ${guildId}`);
    } else {
      // Fetch existing global commands so we can preserve any Entry Point
      // commands (type 4). A plain bulk PUT that omits them triggers error
      // 50240 on apps that have a Discord Activity / App Launcher entry point.
      const existing = await rest.get(Routes.applicationCommands(c.user.id)) as Array<Record<string, unknown>>;
      const entryPoints = existing
        .filter((cmd) => cmd['type'] === 4)
        .map((cmd) => Object.fromEntries(Object.entries(cmd).filter(([k]) => !RO_KEYS.has(k))));

      await rest.put(Routes.applicationCommands(c.user.id), {
        body: [...SLASH_COMMANDS, ...entryPoints],
      });
      console.log(`[IHTX-TS] Slash commands registered globally (preserved ${entryPoints.length} entry point(s))`);
    }
  } catch (err) {
    console.error('[IHTX-TS] Failed to register slash commands:', err);
  }
});

// ── Prefix command dispatcher ────────────────────────────────────────────────

client.on('messageCreate', async (message: Message) => {
  if (message.author.bot) return;
  if (!message.content.startsWith(PREFIX)) return;

  const body = message.content.slice(PREFIX.length).trimStart();
  const spaceIdx = body.search(/\s/);
  const command = (spaceIdx === -1 ? body : body.slice(0, spaceIdx)).toLowerCase();
  const rest = spaceIdx === -1 ? '' : body.slice(spaceIdx + 1);
  const args = rest.trim() ? rest.trim().split(/\s+/) : [];

  try {
    switch (command) {
      case 'ytdl':
      case 'youtubedownload':
        await runYtdl(message);
        break;

      case 'multipitchihtx':
        await handleMultipitchIHTX(message, args, BOT_OWNER_ID);
        break;

      case 'help':
        await handleHelp(message, BOT_OWNER_ID);
        break;

      case 'coinflip':
      case 'cf':
        await handleCoinflip(message, BOT_OWNER_ID);
        break;

      case 'dice':
      case 'roll':
        await handleDice(message, args, BOT_OWNER_ID);
        break;

      case 'rps':
        await handleRPS(message, args, BOT_OWNER_ID);
        break;

      case '8ball':
        await handleEightBall(message, args, BOT_OWNER_ID);
        break;

      case 'slots':
      case 'slot':
        await handleSlots(message, BOT_OWNER_ID);
        break;

      case 'choose':
      case 'pick': {
        const chooseArgs = rest.trim() ? [rest.trim()] : [];
        await handleChoose(message, chooseArgs, BOT_OWNER_ID);
        break;
      }

      case 'roulette':
        await handleRoulette(message, args, BOT_OWNER_ID);
        break;

      case 'trivia':
        await handleTrivia(message, BOT_OWNER_ID);
        break;

      case 'info':
        await handleInfo(message);
        break;

      case 'chat':
      case 'ask': {
        const chatArgs = rest.trim() ? [rest.trim()] : [];
        await handleChat(message, chatArgs);
        break;
      }

      case 'clearchat':
      case 'resetai':
      case 'chatclear':
        await handleClearchat(message);
        break;

      case 'catbox':
      case 'cb':
      case 'upload':
        await handleCatbox(message, args);
        break;

      case 'bytebeat':
      case 'bb':
        await handleBytebeat(message, rest);
        break;

      case 'ffmpegprocess':
      case 'fmp':
        await handleFfmpegProcess(message, rest);
        break;

      case 'realgmajor4':
      case 'realgm4':
      case 'rgm4':
        await handleRealGMajor4(message);
        break;

      case 'multipitch2':
      case 'mp2':
        await handleMultipitch2(message, rest);
        break;

      case 'ihtxsap':
      case 'sap':
        await handleIhtxSap(message);
        break;

      case 'stretch_to_length':
      case 'stl':
        await handleStretchToLength(message, rest);
        break;

      default:
        break;
    }
  } catch (err) {
    console.error(`[IHTX-TS] Unhandled error in command "${command}":`, err);
    try {
      await message.reply('❌ An unexpected error occurred. Please try again.');
    } catch {
    }
  }
});

// ── Slash command dispatcher ─────────────────────────────────────────────────

client.on('interactionCreate', async (interaction: Interaction) => {
  if (!interaction.isChatInputCommand()) return;
  const slash = interaction as ChatInputCommandInteraction;

  try {
    switch (slash.commandName) {
      case 'bytebeat':
        await handleBytebeatInteraction(slash);
        break;
      case 'ihtxsap':
        await handleIhtxSapInteraction(slash);
        break;
      default:
        break;
    }
  } catch (err) {
    console.error(`[IHTX-TS] Unhandled slash error in "/${slash.commandName}":`, err);
    try {
      const msg = '❌ An unexpected error occurred.';
      if (slash.deferred || slash.replied) await slash.editReply(msg);
      else await slash.reply({ content: msg, ephemeral: true });
    } catch {
    }
  }
});

// ── Error handler ────────────────────────────────────────────────────────────

client.on('error', (err) => {
  console.error('[IHTX-TS] Client error:', err);
});

client.login(BOT_TOKEN).catch((err) => {
  console.error('[IHTX-TS] Failed to log in:', err);
  process.exit(1);
});
