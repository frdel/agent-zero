export function formatOutputSpeed(value) {
  const rate = Number(value);
  if (!Number.isFinite(rate) || rate <= 0) return "";
  return `${rate >= 100 ? Math.round(rate) : rate.toFixed(1)} tok/s`;
}

export function outputSpeedLabel(speed) {
  const text = formatOutputSpeed(speed?.tokens_per_second);
  if (!text) return null;
  const tokens = Number(speed.output_tokens);
  const seconds = Number(speed.seconds);
  const title = Number.isFinite(tokens) && Number.isFinite(seconds)
    ? `${tokens} output tokens in ${seconds.toFixed(1)} s`
    : text;
  return { text, title };
}
