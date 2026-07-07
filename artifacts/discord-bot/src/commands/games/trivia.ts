import { Message, ActionRowBuilder, ButtonBuilder, ButtonStyle, ComponentType } from 'discord.js';
import https from 'https';
import { gameEmbed } from '../../utils/embed.js';

interface TriviaResult {
  category: string;
  difficulty: 'easy' | 'medium' | 'hard';
  question: string;
  correct_answer: string;
  incorrect_answers: string[];
}

function decodeHtml(str: string): string {
  return str
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#039;/g, "'")
    .replace(/&ldquo;/g, '"')
    .replace(/&rdquo;/g, '"')
    .replace(/&apos;/g, "'");
}

function fetchTrivia(): Promise<TriviaResult> {
  return new Promise((resolve, reject) => {
    const req = https.get(
      'https://opentdb.com/api.php?amount=1&type=multiple',
      { timeout: 8000 },
      (res) => {
        let data = '';
        res.on('data', (chunk) => { data += chunk; });
        res.on('end', () => {
          try {
            const parsed = JSON.parse(data);
            if (parsed.response_code !== 0 || !parsed.results?.length) {
              reject(new Error('No trivia results'));
              return;
            }
            resolve(parsed.results[0] as TriviaResult);
          } catch {
            reject(new Error('Failed to parse trivia response'));
          }
        });
      },
    );
    req.on('error', reject);
    req.on('timeout', () => { req.destroy(); reject(new Error('Trivia request timed out')); });
  });
}

const DIFF_COLORS = { easy: 0x57f287, medium: 0xfee75c, hard: 0xed4245 } as const;
const DIFF_EMOJI = { easy: '🟢', medium: '🟡', hard: '🔴' } as const;
const LABELS = ['A', 'B', 'C', 'D'];

export async function handleTrivia(message: Message, ownerId: string): Promise<void> {
  const fetching = await message.reply('⏳ Fetching a trivia question…');

  let trivia: TriviaResult;
  try {
    trivia = await fetchTrivia();
  } catch {
    await fetching.edit('❌ Could not fetch a trivia question. Try again in a moment.');
    return;
  }

  const question = decodeHtml(trivia.question);
  const correct = decodeHtml(trivia.correct_answer);
  const allAnswers = [correct, ...trivia.incorrect_answers.map(decodeHtml)]
    .sort(() => Math.random() - 0.5);
  const correctIndex = allAnswers.indexOf(correct);

  const embed = gameEmbed(message, ownerId, {
    title: '🧠 Trivia',
    color: DIFF_COLORS[trivia.difficulty],
    fields: [
      { name: 'Category', value: trivia.category, inline: true },
      { name: 'Difficulty', value: `${DIFF_EMOJI[trivia.difficulty]} ${trivia.difficulty}`, inline: true },
      { name: 'Question', value: question },
      {
        name: 'Options',
        value: allAnswers.map((a, i) => `**${LABELS[i]}.** ${a}`).join('\n'),
      },
    ],
    footer: 'IHTX Games • Trivia — You have 30 seconds',
  });

  const buttons = new ActionRowBuilder<ButtonBuilder>().addComponents(
    allAnswers.map((_, i) =>
      new ButtonBuilder()
        .setCustomId(`trivia_${i}`)
        .setLabel(LABELS[i])
        .setStyle(ButtonStyle.Primary),
    ),
  );

  await fetching.edit({ content: '', embeds: [embed], components: [buttons] });

  const collector = fetching.createMessageComponentCollector({
    componentType: ComponentType.Button,
    filter: (btn) => btn.user.id === message.author.id,
    time: 30_000,
    max: 1,
  });

  collector.on('collect', async (btn) => {
    const chosen = parseInt(btn.customId.replace('trivia_', ''), 10);
    const isCorrect = chosen === correctIndex;

    const resultEmbed = gameEmbed(message, ownerId, {
      title: `🧠 Trivia — ${isCorrect ? '✅ Correct!' : '❌ Wrong!'}`,
      color: isCorrect ? 0x57f287 : 0xed4245,
      fields: [
        { name: 'Question', value: question },
        { name: 'Your answer', value: `**${LABELS[chosen]}.** ${allAnswers[chosen]}`, inline: true },
        { name: 'Correct answer', value: `**${LABELS[correctIndex]}.** ${correct}`, inline: true },
      ],
      footer: 'IHTX Games • Trivia',
    });

    await btn.update({ embeds: [resultEmbed], components: [] });
  });

  collector.on('end', async (collected) => {
    if (collected.size === 0) {
      const timeoutEmbed = gameEmbed(message, ownerId, {
        title: '🧠 Trivia — ⏰ Time\'s up!',
        color: 0x888888,
        fields: [
          { name: 'Question', value: question },
          { name: 'Correct answer', value: `**${LABELS[correctIndex]}.** ${correct}` },
        ],
        footer: 'IHTX Games • Trivia',
      });
      await fetching.edit({ embeds: [timeoutEmbed], components: [] }).catch(() => {});
    }
  });
}
