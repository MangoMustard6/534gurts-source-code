import { readFileSync, writeFileSync, existsSync, mkdirSync } from "node:fs";
import { join } from "node:path";
import { Message } from "discord.js";
import { BOT_OWNER_ID } from "../config.js";

const DATA_DIR = "/home/runner/workspace/data";
const CHANNEL_BLOCKS_FILE = join(DATA_DIR, "channel_blocks.json");

interface BlockEntry {
  until: number;
  username: string;
}

type ChannelBlockStore = Record<string, Record<string, BlockEntry>>;

function load(): ChannelBlockStore {
  if (!existsSync(CHANNEL_BLOCKS_FILE)) return {};
  try {
    return JSON.parse(readFileSync(CHANNEL_BLOCKS_FILE, "utf-8")) as ChannelBlockStore;
  } catch {
    return {};
  }
}

function save(store: ChannelBlockStore): void {
  if (!existsSync(DATA_DIR)) mkdirSync(DATA_DIR, { recursive: true });
  writeFileSync(CHANNEL_BLOCKS_FILE, JSON.stringify(store, null, 2), "utf-8");
}

export function isBlockedInChannel(userId: string, channelId: string): boolean {
  const store = load();
  const channel = store[channelId];
  if (!channel) return false;
  const entry = channel[userId];
  if (!entry) return false;
  if (Date.now() >= entry.until) {
    delete channel[userId];
    if (Object.keys(channel).length === 0) delete store[channelId];
    save(store);
    return false;
  }
  return true;
}

export function getChannelBlockInfo(
  userId: string,
  channelId: string,
): BlockEntry | null {
  const store = load();
  const channel = store[channelId];
  if (!channel) return null;
  const entry = channel[userId];
  if (!entry) return null;
  if (Date.now() >= entry.until) return null;
  return entry;
}

async function requireOwner(message: Message): Promise<boolean> {
  if (BOT_OWNER_ID && message.author.id === BOT_OWNER_ID) return true;
  await message.reply("❌ Only the bot owner can use this command.");
  return false;
}

async function resolveTarget(
  message: Message,
  targetRaw: string,
): Promise<{ id: string; username: string } | null> {
  const mentionMatch = /^<@!?(\d+)>$/.exec(targetRaw);

  if (mentionMatch) {
    const id = mentionMatch[1]!;
    const member =
      message.guild?.members.cache.get(id) ??
      (await message.guild?.members.fetch(id).catch(() => null));
    return { id, username: member?.user.username ?? id };
  }

  if (/^\d+$/.test(targetRaw)) {
    const member =
      message.guild?.members.cache.get(targetRaw) ??
      (await message.guild?.members.fetch(targetRaw).catch(() => null));
    return { id: targetRaw, username: member?.user.username ?? targetRaw };
  }

  await message.reply("❌ Please specify a user via `@mention` or numeric user ID.");
  return null;
}

export async function handleBlockchannelCommand(message: Message): Promise<void> {
  if (!(await requireOwner(message))) return;

  const channelId = message.channelId;
  const rest = message.content.slice("th/blockchannel".length).trim();
  const parts = rest.split(/\s+/);

  const targetRaw = parts[0] ?? "";
  const hoursRaw = parts[1] ?? "";
  const hours = parseFloat(hoursRaw);

  if (!targetRaw || isNaN(hours) || hours <= 0) {
    await message.reply("❌ Usage: `th/blockchannel <@mention|userId> <hours>`");
    return;
  }

  const target = await resolveTarget(message, targetRaw);
  if (!target) return;

  if (target.id === message.author.id) {
    await message.reply("❌ You cannot block yourself.");
    return;
  }

  const until = Date.now() + Math.round(hours * 3_600_000);
  const store = load();
  if (!store[channelId]) store[channelId] = {};
  store[channelId]![target.id] = { until, username: target.username };
  save(store);

  const unixSec = Math.floor(until / 1000);
  await message.reply(
    `✅ **${target.username}** is blocked from using the bot in this channel for **${hours}h** (until <t:${unixSec}:F>).`,
  );
}

export async function handleUnblockchannelCommand(message: Message): Promise<void> {
  if (!(await requireOwner(message))) return;

  const channelId = message.channelId;
  const rest = message.content.slice("th/unblockchannel".length).trim();
  const targetRaw = rest.trim();

  if (!targetRaw) {
    await message.reply("❌ Usage: `th/unblockchannel <@mention|userId>`");
    return;
  }

  const target = await resolveTarget(message, targetRaw);
  if (!target) return;

  const store = load();
  const channel = store[channelId];
  if (!channel || !channel[target.id]) {
    await message.reply("ℹ️ That user is not currently blocked in this channel.");
    return;
  }
  const name = channel[target.id]!.username;
  delete channel[target.id];
  if (Object.keys(channel).length === 0) delete store[channelId];
  save(store);
  await message.reply(`✅ **${name}** has been unblocked in this channel.`);
}
