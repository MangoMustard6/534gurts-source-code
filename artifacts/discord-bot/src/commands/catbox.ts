import path from 'path';
import fs from 'fs';
import os from 'os';
import { Message, EmbedBuilder, Attachment } from 'discord.js';
import { spawnAsync } from '../utils/spawn.js';
import { BOT_OWNER_ID } from '../config.js';

const CATBOX_UPLOAD_SCRIPT = path.resolve('../../bot/catbox_upload.py');
const MAX_FILE_BYTES = 200 * 1024 * 1024; // catbox.moe limit: 200 MB
const UPLOAD_TIMEOUT_MS = 5 * 60 * 1000;

function makeTempDir(prefix: string): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), `ihtx-${prefix}-`));
}

const ENV_USERHASH = process.env.CATBOX_USERHASH ?? '';

function parseArgs(args: string[]): { userhash: string | null } {
  let userhash: string | null = null;
  for (const arg of args) {
    const eqIdx = arg.indexOf('=');
    if (eqIdx === -1) continue;
    const key = arg.slice(0, eqIdx).toLowerCase().trim();
    const val = arg.slice(eqIdx + 1).trim();
    if (key === 'userhash' && val) userhash = val;
  }
  // Fall back to the secret from environment if no arg supplied
  if (!userhash && ENV_USERHASH) userhash = ENV_USERHASH;
  return { userhash };
}

async function resolveAttachment(message: Message): Promise<Attachment | null> {
  // 1. Direct attachment on this message
  const direct = message.attachments.first();
  if (direct) return direct;

  // 2. Replied-to message attachment
  if (message.reference?.messageId) {
    try {
      const ref = await message.fetchReference();
      const refAttachment = ref.attachments.first();
      if (refAttachment) return refAttachment;
    } catch {
      // reference message not found — fall through
    }
  }

  return null;
}

export async function handleCatbox(message: Message, args: string[]): Promise<void> {
  const ownerId = BOT_OWNER_ID;
  const isOwner = ownerId !== '' && message.author.id === ownerId;
  const { userhash } = parseArgs(args);

  const attachment = await resolveAttachment(message);

  if (!attachment) {
    await message.reply(
      '❌ No file found. Attach a file directly, or reply to a message that has an attachment.\n' +
      'Optional: `userhash=<your_catbox_hash>` to save to your account.',
    );
    return;
  }

  if (attachment.size > MAX_FILE_BYTES) {
    await message.reply(
      `❌ File is ${(attachment.size / 1024 / 1024).toFixed(1)} MB — catbox.moe limit is 200 MB.`,
    );
    return;
  }

  const hashNote = userhash ? ' (saving to your account)' : ' (anonymous)';
  const status = await message.reply(
    `⏳ Downloading **${attachment.name}** (${(attachment.size / 1024 / 1024).toFixed(2)} MB)${hashNote}…`,
  );

  const tmpDir = makeTempDir('catbox');
  const localPath = path.join(tmpDir, attachment.name);

  try {
    const res = await fetch(attachment.url);
    if (!res.ok) throw new Error(`HTTP ${res.status} downloading attachment`);
    fs.writeFileSync(localPath, Buffer.from(await res.arrayBuffer()));

    await status.edit(`⏳ Uploading **${attachment.name}** to catbox.moe…`);

    const scriptArgs = [CATBOX_UPLOAD_SCRIPT, localPath];
    if (userhash) scriptArgs.push(userhash);

    const result = await spawnAsync('python3', scriptArgs, { timeout: UPLOAD_TIMEOUT_MS });

    if (result.code !== 0) {
      await status.edit(`❌ Catbox upload failed.\n\`\`\`\n${result.stderr.slice(-500)}\n\`\`\``);
      return;
    }

    const url = result.stdout.trim();
    if (!url.startsWith('http')) {
      await status.edit(`❌ Unexpected catbox response: \`${url.slice(0, 200)}\``);
      return;
    }

    const sizeMB = (attachment.size / 1024 / 1024).toFixed(2);
    const embed = new EmbedBuilder()
      .setColor(0x2ecc71)
      .setAuthor({
        name: isOwner ? `👑 ${message.author.displayName}` : message.author.displayName,
        iconURL: message.author.displayAvatarURL(),
      })
      .setTitle('✅ Uploaded to catbox.moe')
      .setDescription(`**[${attachment.name}](${url})**`)
      .addFields(
        { name: 'URL', value: url, inline: false },
        { name: 'Size', value: `${sizeMB} MB`, inline: true },
        { name: 'Type', value: attachment.contentType ?? 'unknown', inline: true },
        { name: 'Account', value: userhash ? '🔑 Your account' : '🌐 Anonymous', inline: true },
      )
      .setFooter({ text: 'catbox.moe — permanent direct link' })
      .setTimestamp();

    await status.edit({ content: '', embeds: [embed] });
  } finally {
    try { fs.rmSync(tmpDir, { recursive: true, force: true }); } catch { }
  }
}
