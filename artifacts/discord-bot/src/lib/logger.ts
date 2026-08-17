type Level = 'info' | 'warn' | 'error';

function log(level: Level, obj: Record<string, unknown>, msg?: string): void {
  const ts = new Date().toISOString();
  const extra = Object.keys(obj).length ? ' ' + JSON.stringify(obj) : '';
  const line = `[${ts}] ${level.toUpperCase()} ${msg ?? ''}${extra}`;
  if (level === 'error') console.error(line);
  else console.log(line);
}

export const logger = {
  info: (obj: Record<string, unknown>, msg?: string) => log('info', obj, msg),
  warn: (obj: Record<string, unknown>, msg?: string) => log('warn', obj, msg),
  error: (obj: Record<string, unknown>, msg?: string) => log('error', obj, msg),
};
