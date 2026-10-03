export function todayInSaoPaulo(): string {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/Sao_Paulo', year: 'numeric', month: '2-digit', day: '2-digit',
  }).formatToParts(new Date());
  const part = (type: string) => parts.find((value) => value.type === type)!.value;
  return `${part('year')}-${part('month')}-${part('day')}`;
}

export function nextMonth(value: string): string {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return '';
  const [year, month, day] = value.split('-').map(Number);
  if (year < 100 || year >= 9999 || month < 1 || month > 12 || day < 1) return '';
  const lastDay = new Date(year, month, 0).getDate();
  if (day > lastDay) return '';
  const nextYear = year + (month === 12 ? 1 : 0);
  const next = month === 12 ? 1 : month + 1;
  const clamped = Math.min(day, new Date(nextYear, next, 0).getDate());
  return `${nextYear}-${String(next).padStart(2, '0')}-${String(clamped).padStart(2, '0')}`;
}
