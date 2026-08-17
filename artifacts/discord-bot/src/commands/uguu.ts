import fs from 'fs';
import os from 'os';
import path from 'path';
import { Attachment, Message } from 'discord.js';
import { uploadToUguu } from '../utils/catbox.js';

function makeTempDir(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'ihtx-uguu-'));
}

async function resolveAttachment(message: Message): Promise<Attachment | null> {
  const direct = message.attachments.first();
  if (direct) return direct;
  if (message.reference?.messageId) {
    try {
      const reference = await message.fetchReference();
      return reference.attachments.first() ?? null;
    } catch {
      return null;
    }
  }
  return null;
}

export async function handleUguu(message: Message): Promise<void> {
  const attachment = await resolveAttachment(message);
  if (!attachment) {
    await message.reply('❌ No file found. Attach a file directly, or reply to a message with a file to upload to uguu.se.');
    return;
  }

  const status = await message.reply(`⏳ Downloading **${attachment.name}** and uploading it to uguu.se…`);
  const tmpDir = makeTempDir();
  const localPath = path.join(tmpDir, attachment.name);
  try {
    const res = await fetch(attachment.url, { signal: AbortSignal.timeout(120_000) });
    if (!res.ok) throw new Error(`HTTP ${res.status} downloading attachment`);
    fs.writeFileSync(localPath, Buffer.from(await res.arrayBuffer()));
    const url = await uploadToUguu(localPath);
    await status.edit(
      url
        ? `✅ Uploaded to **uguu.se**\n${url}`
        : '❌ Uguu upload failed.',
    );
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    await status.edit(`❌ Uguu upload failed: ${detail.slice(0, 300)}`);
  } finally {
    try { fs.rmSync(tmpDir, { recursive: true, force: true }); } catch { }
  }
}