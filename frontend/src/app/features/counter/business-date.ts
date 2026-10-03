/** Data de negócio atual (America/Sao_Paulo) em `YYYY-MM-DD`, o mesmo calendário usado pelo backend. */
export function businessToday(now: Date = new Date()): string {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: 'America/Sao_Paulo',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(now);
}
