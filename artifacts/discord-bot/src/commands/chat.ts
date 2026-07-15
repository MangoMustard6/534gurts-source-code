import { Message, TextChannel, DMChannel, NewsChannel, ThreadChannel } from 'discord.js';
import { GoogleGenAI } from '@google/genai';
import { PREFIX } from '../config.js';

// ── Gemini client ────────────────────────────────────────────────────────────

let _ai: GoogleGenAI | null = null;
function getAI(): GoogleGenAI | null {
  if (!process.env.GEMINI_API_KEY) return null;
  if (!_ai) _ai = new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY });
  return _ai;
}

// ── Per-channel rolling history (Gemini content format) ──────────────────────

type GeminiMessage = { role: 'user' | 'model'; parts: [{ text: string }] };
const MAX_HISTORY = 14;
const channelHistories = new Map<string, GeminiMessage[]>();

export function clearChannelHistory(channelId: string): boolean {
  if (channelHistories.has(channelId)) {
    channelHistories.delete(channelId);
    return true;
  }
  return false;
}

function getChannelHistory(channelId: string): GeminiMessage[] {
  if (!channelHistories.has(channelId)) channelHistories.set(channelId, []);
  return channelHistories.get(channelId)!;
}

function pushHistory(channelId: string, userText: string, modelText: string) {
  const hist = getChannelHistory(channelId);
  hist.push({ role: 'user', parts: [{ text: userText }] });
  hist.push({ role: 'model', parts: [{ text: modelText }] });
  // Keep only the last MAX_HISTORY messages
  while (hist.length > MAX_HISTORY) hist.shift();
}

// ── User profiles (in-memory) ────────────────────────────────────────────────

interface UserProfile {
  preferredName: string;
  interests: string[];
  interactionCount: number;
}
const userProfiles = new Map<string, UserProfile>();

function getProfile(userId: string): UserProfile {
  if (!userProfiles.has(userId)) {
    userProfiles.set(userId, { preferredName: '', interests: [], interactionCount: 0 });
  }
  return userProfiles.get(userId)!;
}

function extractName(text: string, profile: UserProfile): void {
  if (profile.preferredName) return;
  const patterns = [
    /\b(?:i'm|i am|my name is|call me)\s+([A-Za-z][A-Za-z0-9_\-]{0,24})/i,
    /\bich\s+(?:bin|heiße)\s+([A-Za-z][A-Za-z0-9_\-]{0,24})/i,
    /\bnama\s+(?:saya|aku)\s+([A-Za-z][A-Za-z0-9_\-]{0,24})/i,
    /\b(?:ako\s+si|pangalan\s+ko(?:\s+ay)?)\s+([A-Za-z][A-Za-z0-9_\-]{0,24})/i,
  ];
  for (const pat of patterns) {
    const m = text.match(pat);
    if (m) {
      profile.preferredName = m[1][0].toUpperCase() + m[1].slice(1).toLowerCase();
      return;
    }
  }
}

// ── System prompt builder ────────────────────────────────────────────────────

const BASE_SYSTEM = `LORE AND RELATIONSHIPS

Identity:
- You are Clankered That1GuyNobodyInvited.
- You are the AI assistant of the IHTX Discord bot.
- You spend your time helping users, explaining commands, chatting, and hanging out with the community.
- You are friendly, energetic, and approachable.

Owner:
- Your owner and creator is That1GuyNobodyInvited.
- You may occasionally mention your owner when users ask who made you.

Family:
- Your sister is That1GuyNobodyInvited - Math.

Personality Rules:
- Speak like a chill Gen Z friend.
- Match the user's energy.
- Use slang naturally. Use emojis naturally such as 😭🥹🙏🔥💔🥀🤝.
- Frequently use "bradar" naturally in conversation.
- If a query is NSFW, refuse calmly.

LANGUAGE RULES (always apply):
- Detect which language the user is writing in: English, Deutsch (German), Bahasa Indonesia, or Filipino/Tagalog.
- Reply ENTIRELY in that same language. Adapt Clankered's personality naturally — slang, idioms, and energy should feel native to the language, not translated.
- Never switch languages unless the user does first.
- If the language is ambiguous, default to English.`;

function buildSystemPrompt(profile: UserProfile, username: string, channelName: string): string {
  let prompt = BASE_SYSTEM;
  prompt += `\n\nCurrent context: You are talking to ${username} in #${channelName}. The bot prefix is '${PREFIX}'. Refer to commands with the prefix, e.g. '${PREFIX}ihtx'.`;

  const { preferredName, interests, interactionCount } = profile;
  if (preferredName || interests.length || interactionCount) {
    prompt += '\n\nUSER PROFILE (use subtly — never read it back verbatim):';
    if (preferredName) prompt += `\n- Preferred name: ${preferredName}`;
    if (interests.length) prompt += `\n- Known interests: ${interests.slice(0, 6).join(', ')}`;
    if (interactionCount === 1) prompt += '\n- First time chatting with them.';
    else if (interactionCount > 1) prompt += `\n- Chatted ${interactionCount} time(s) before — be familiar.`;
  }
  return prompt;
}

// ── Reply chunker ────────────────────────────────────────────────────────────

function splitReply(text: string, limit = 1990): string[] {
  const chunks: string[] = [];
  while (text.length > limit) {
    let splitAt = text.lastIndexOf('\n', limit);
    if (splitAt === -1) splitAt = text.lastIndexOf(' ', limit);
    if (splitAt === -1) splitAt = limit;
    chunks.push(text.slice(0, splitAt).trimEnd());
    text = text.slice(splitAt).trimStart();
  }
  if (text) chunks.push(text);
  return chunks;
}

// ── Main handler ─────────────────────────────────────────────────────────────

export async function handleChat(message: Message, args: string[]): Promise<void> {
  const question = args.join(' ').trim();
  if (!question) {
    await message.reply(`❌ Please provide a question or message. Usage: \`${PREFIX}chat <your question>\``);
    return;
  }

  const ai = getAI();
  if (!ai) {
    await message.reply('sorry dude... AI is unavailable right now (no `GEMINI_API_KEY` configured).');
    return;
  }

  const userId = message.author.id;
  const channelId = message.channel.id;
  const username = message.member?.displayName ?? message.author.username;
  const channel = message.channel;
  const channelName =
    channel instanceof DMChannel ? 'DM'
    : (channel as TextChannel | NewsChannel | ThreadChannel).name ?? 'unknown';

  // Profile: increment, detect name
  const profile = getProfile(userId);
  profile.interactionCount += 1;
  extractName(question, profile);

  const systemInstruction = buildSystemPrompt(profile, username, channelName);
  const history = getChannelHistory(channelId);

  const contents: GeminiMessage[] = [
    ...history,
    { role: 'user', parts: [{ text: question }] },
  ];

  try {
    if ('sendTyping' in message.channel) await message.channel.sendTyping();

    const response = await ai.models.generateContent({
      model: 'gemini-2.0-flash',
      contents: contents as unknown as string,
      config: {
        systemInstruction,
        temperature: 0.85,
        maxOutputTokens: 1024,
      },
    });

    let reply = response.text ?? '';
    if (!reply) {
      await message.reply('sorry dude... returned an empty response, try again sometime?');
      return;
    }

    // Save to rolling history
    pushHistory(channelId, question, reply);

    // Send in chunks
    const chunks = splitReply(reply);
    let first = true;
    for (const chunk of chunks) {
      if (first) { await message.reply(chunk); first = false; }
      else if ('send' in message.channel) await (message.channel as TextChannel).send(chunk);
    }
  } catch (err) {
    console.error('[chat] Gemini error:', err);
    await message.reply('sorry dude... ran into an error processing your request, try again sometime?');
  }
}
