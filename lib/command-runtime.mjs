import { pathToFileURL } from 'node:url';

export const EXIT_CODES = {
  OK: 0,
  USAGE: 1,
  RENDER_BLOCKED: 2,
  ANALYSIS_BLOCKED: 3,
  CRITIQUE_FAILED: 4,
  INTERNAL_ERROR: 5,
};

export class CommandError extends Error {
  constructor(message, options = {}) {
    super(message);
    this.name = 'CommandError';
    this.exitCode = options.exitCode ?? EXIT_CODES.USAGE;
    this.code = options.code ?? 'command_error';
    this.details = options.details ?? null;
  }
}

export function parseCommonArgs(argv) {
  const flags = {
    json: false,
    quiet: false,
    verbose: false,
  };
  const positionals = [];

  for (let index = 0; index < argv.length; index += 1) {
    const value = argv[index];
    if (value === '--json') {
      flags.json = true;
      continue;
    }
    if (value === '--quiet') {
      flags.quiet = true;
      continue;
    }
    if (value === '--verbose') {
      flags.verbose = true;
      continue;
    }
    positionals.push(value);
  }

  return {
    flags,
    positionals,
  };
}

export function printResult(result, flags = {}) {
  if (flags.json) {
    process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
    return;
  }

  if (flags.quiet) {
    return;
  }

  if (Array.isArray(result.messages) && result.messages.length > 0) {
    result.messages.forEach((message) => {
      process.stdout.write(`${message}\n`);
    });
    return;
  }

  if (result.message) {
    process.stdout.write(`${result.message}\n`);
  }
}

export function printError(error, flags = {}) {
  const payload = {
    status: 'error',
    code: error.code ?? 'command_error',
    exit_code: error.exitCode ?? EXIT_CODES.USAGE,
    message: error.message,
    details: error.details ?? null,
  };

  if (flags.json) {
    process.stdout.write(`${JSON.stringify(payload, null, 2)}\n`);
    return;
  }

  process.stderr.write(`${error.message}\n`);
  if (flags.verbose && error.details) {
    process.stderr.write(`${JSON.stringify(error.details, null, 2)}\n`);
  }
}

export async function runCliCommand(handler, argv = process.argv.slice(2)) {
  const { flags, positionals } = parseCommonArgs(argv);
  try {
    const result = await handler({
      argv,
      flags,
      positionals,
    });
    printResult(result, flags);
    return result.exitCode ?? EXIT_CODES.OK;
  } catch (error) {
    const commandError =
      error instanceof CommandError
        ? error
        : new CommandError(error?.message ?? String(error), {
            exitCode: EXIT_CODES.INTERNAL_ERROR,
            code: 'unexpected_error',
          });
    printError(commandError, flags);
    return commandError.exitCode;
  }
}

export function isMainModule(importMetaUrl) {
  return process.argv[1] ? importMetaUrl === pathToFileURL(process.argv[1]).href : false;
}
