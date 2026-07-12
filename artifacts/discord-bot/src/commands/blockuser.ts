import { readFileSync, writeFileSync, existsSync, mkdirSync } from "node:fs";
import { join } from "node:path";
import { Message } from "discord.js";
import { BOT_OWNER_ID } from "../config.js";

const DATA_DIR = "/home/runner/workspace/data";
const BLOCKS_FILE = join(DATA_DIR, "blocks.json");

interface BlockEntry {
  until: number;
  username: string;
}

type BlockStore = Record<string, BlockEntry>;

function load(): BlockStore {
  if (!existsSync(BLOCKS_FILE)) return {};
  try {
    return JSON.parse(readFileSync(BLOCKS_FILE, "utf-8")) as BlockStore;
  } catch {
    return {};
  }
}

function save(store: BlockStore): void {
  if (!existsSync(DATA_DIR)) mkdirSync(DATA_DIR, { recursive: true });
  writeFileSync(BLOCKS_FILE, JSON.stringify(store, null, 2), "utf-8");
}

export function isBlocked(userId: string): boolean {
  const store = load();
  const entry = store[userId];
  if (!entry) return false;
  if (Date.now() >= entry.until) {
    delete store[userId];
    save(store);
    return false;
  }
  return true;
}

export function getBlockInfo(userId: string): BlockEntry | null {
  const store = load();
  const entry = store[userId];
  if (!entry) return null;
  if (Date.now() >= entry.until) return null;
  return entry;
}

function requireOwner(message: Message): boolean {
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

export async function handleBlockuserCommand(message: Message): Promise<void> {
  if (!requireOwner(message)) return;

  const rest = message.content.slice("th/blockuser".length).trim();
  const parts = rest.split(/\s+/);

  const targetRaw = parts[0] ?? "";
  const hoursRaw = parts[1] ?? "";
  const hours = parseFloat(hoursRaw);

  if (!targetRaw || isNaN(hours) || hours <= 0) {
    await message.reply("❌ Usage: `th/blockuser <@mention|userId> <hours>`");
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
  store[target.id] = { until, username: target.username };
  save(store);

  const unixSec = Math.floor(until / 1000);
  await message.reply(
    `✅ **${target.username}** is globally blocked from using the bot for **${hours}h** (until <t:${unixSec}:F>).`,
  );
}

export async function handleUnblockuserCommand(message: Message): Promise<void> {
  if (!requireOwner(message)) return;

  const rest = message.content.slice("th/unblockuser".length).trim();
  const targetRaw = rest.trim();

  if (!targetRaw) {
    await message.reply("❌ Usage: `th/unblockuser <@mention|userId>`");
    return;
  }

  const target = await resolveTarget(message, targetRaw);
  if (!target) return;

  const store = load();
  if (!store[target.id]) {
    await message.reply("ℹ️ That user is not currently globally blocked.");
    return;
  }
  const name = store[target.id]!.username;
  delete store[target.id];
  save(store);
  await message.reply(`✅ **${name}** has been globally unblocked.`);
}
