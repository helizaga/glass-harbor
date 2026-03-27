export function sanitizeSlug(value) {
  return `${value ?? ''}`
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

export function parseSongMetadata(code) {
  const metadata = {};
  const matches = code.matchAll(/^\/\/\s*@([\w-]+)\s+(.+)$/gm);
  for (const [, key, value] of matches) {
    metadata[key.trim().toLowerCase()] = value.trim();
  }
  return metadata;
}

export function parseSections(sectionValue) {
  if (!sectionValue) {
    return [];
  }

  return sectionValue
    .split(',')
    .map((entry) => entry.trim())
    .filter(Boolean)
    .map((entry) => {
      const match = entry.match(/^([a-z0-9-]+)\s*:\s*(\d+)$/i);
      if (!match) {
        throw new Error(`Invalid @sections entry: ${entry}`);
      }

      return {
        name: sanitizeSlug(match[1]),
        cycles: Number.parseInt(match[2], 10),
      };
    });
}

export function buildSectionTimeline(sectionDefs) {
  let begin = 0;
  return sectionDefs.map((section) => {
    const timelineEntry = {
      ...section,
      begin,
      end: begin + section.cycles,
    };
    begin = timelineEntry.end;
    return timelineEntry;
  });
}

function uniqueSorted(values) {
  return [...new Set(values.filter(Boolean))].sort((left, right) => left.localeCompare(right));
}

function extractDependencyTokens(raw) {
  return uniqueSorted(
    [...`${raw ?? ''}`.toLowerCase().matchAll(/[a-z_][a-z0-9_-]*/g)].map(([token]) => token),
  );
}

export function extractSampleRoles(code) {
  return uniqueSorted(
    [...`${code ?? ''}`.matchAll(/(^|[^\w.])s\s*\(\s*(['"`])([\s\S]*?)\2\s*\)/gm)].flatMap((match) =>
      extractDependencyTokens(match[3]),
    ),
  );
}

export function extractSynthVoices(code) {
  return uniqueSorted(
    [...`${code ?? ''}`.matchAll(/\.sound\s*\(\s*(['"`])([\s\S]*?)\1\s*\)/gm)].flatMap((match) =>
      extractDependencyTokens(match[2]),
    ),
  );
}

export function collectAudioDependencies(code) {
  return {
    sampleRoles: extractSampleRoles(code),
    synthVoices: extractSynthVoices(code),
  };
}
