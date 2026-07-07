import { spawn } from 'child_process';

export interface SpawnResult {
  stdout: string;
  stderr: string;
  code: number;
}

export interface SpawnOptions {
  timeout?: number;
  cwd?: string;
}

export function spawnAsync(
  cmd: string,
  args: string[],
  options: SpawnOptions = {},
): Promise<SpawnResult> {
  return new Promise((resolve, reject) => {
    let proc: ReturnType<typeof spawn>;

    try {
      proc = spawn(cmd, args, {
        cwd: options.cwd,
        stdio: ['ignore', 'pipe', 'pipe'],
        shell: false,
      });
    } catch (err) {
      reject(new Error(`Failed to spawn "${cmd}": ${String(err)}`));
      return;
    }

    let stdout = '';
    let stderr = '';
    let settled = false;

    const settle = (result: SpawnResult | Error) => {
      if (settled) return;
      settled = true;
      if (timer) clearTimeout(timer);
      if (result instanceof Error) reject(result);
      else resolve(result);
    };

    const timer = options.timeout
      ? setTimeout(() => {
          proc.kill('SIGKILL');
          settle(new Error(`Process "${cmd}" timed out after ${options.timeout}ms`));
        }, options.timeout)
      : null;

    proc.stdout?.on('data', (d: Buffer) => { stdout += d.toString(); });
    proc.stderr?.on('data', (d: Buffer) => { stderr += d.toString(); });

    proc.on('close', (code) => {
      settle({ stdout, stderr, code: code ?? 1 });
    });

    proc.on('error', (err) => {
      settle(new Error(`spawn error for "${cmd}": ${err.message}`));
    });
  });
}
