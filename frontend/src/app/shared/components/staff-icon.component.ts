import { ChangeDetectionStrategy, Component, input } from '@angular/core';

const PATHS: Record<string, string> = {
  home: 'M3 10 12 3l9 7v11h-6v-7H9v7H3Z',
  book: 'M12 5v16M3 4h5a4 4 0 0 1 4 2 4 4 0 0 1 4-2h5v15h-5a4 4 0 0 0-4 2 4 4 0 0 0-4-2H3Z',
  users: 'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M16 3a4 4 0 0 1 0 8M22 21v-2a4 4 0 0 0-3-3.87M13 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0',
  exchange: 'M4 7h16l-4-4M20 17H4l4 4',
  return: 'M9 4 4 9l5 5M4 9h11a5 5 0 0 1 0 10h-3',
  cart: 'M2 3h3l3 12h11l3-9H6M10 20h.01M18 20h.01',
  bookmark: 'M6 3h12v19l-6-4-6 4Z',
  logout: 'M9 3H3v18h6M13 7l5 5-5 5M8 12h13',
  search: 'M21 21l-5-5M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0',
  bell: 'M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4',
  plus: 'M12 5v14M5 12h14',
  chart: 'M4 21V11h4v10M10 21V3h4v18M16 21V7h4v14',
  star: 'm12 3 3 6 7 1-5 5 1 7-6-3-6 3 1-7-5-5 7-1Z',
  clock: 'M12 8v5l3 2M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0',
};
@Component({ selector: 'app-staff-icon', standalone: true, changeDetection: ChangeDetectionStrategy.OnPush,
  template: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path [attr.d]="path()" /></svg>',
  styles: [':host{display:inline-flex;width:22px;height:22px;flex-shrink:0}svg{width:100%;height:100%}'],
})
export class StaffIconComponent {
  readonly name = input('book');
  protected path(): string { return PATHS[this.name()] ?? PATHS['book']; }
}
