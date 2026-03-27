export async function reviewAudioWithProvider() {
  const provider = (process.env.GLASS_HARBOR_AUDIO_REVIEW_PROVIDER ?? 'none').trim().toLowerCase();
  if (!provider || provider === 'none') {
    return {
      provider: 'none',
      summary: null,
      notes: [],
    };
  }

  return {
    provider,
    summary: `Provider "${provider}" is not configured in-repo yet. Falling back to MIR-only critique.`,
    notes: [],
  };
}
