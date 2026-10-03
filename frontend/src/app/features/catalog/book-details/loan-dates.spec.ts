import { nextMonth } from './loan-dates';

describe('Prazo de um mês de calendário', () => {
  it('ajusta dias no fim do mês e considera anos bissextos', () => {
    expect(nextMonth('2026-01-31')).toBe('2026-02-28');
    expect(nextMonth('2028-01-31')).toBe('2028-02-29');
    expect(nextMonth('2026-12-31')).toBe('2027-01-31');
    expect(nextMonth('2026-10-03')).toBe('2026-11-03');
  });
  it('rejeita datas inexistentes e entrada incompleta', () => {
    for (const value of ['', '2026-02-31', '2026-13-01', '2026-00-03', 'texto']) expect(nextMonth(value)).toBe('');
  });
});
