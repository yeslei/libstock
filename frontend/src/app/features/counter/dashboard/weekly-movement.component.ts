import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { MovementDay } from './dashboard.models';
@Component({
  selector: 'app-weekly-movement',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <svg
      viewBox="0 0 560 230"
      role="img"
      aria-label="Empréstimos e devoluções dos últimos sete dias"
    >
      @for (tick of ticks; track tick) {
        <line
          x1="30"
          x2="550"
          [attr.y1]="190 - tick * 160"
          [attr.y2]="190 - tick * 160"
          stroke="#eee9df"
        />
        <text x="20" [attr.y]="194 - tick * 160" text-anchor="end">
          {{ rounded(scale() * tick) }}
        </text>
      }
      @for (day of days(); track day.date; let i = $index) {
        <g>
          <rect
            [attr.x]="48 + i * 71"
            [attr.y]="190 - (day.loans / scale()) * 160"
            width="23"
            [attr.height]="(day.loans / scale()) * 160"
            rx="4"
            fill="#194c38"
          >
            <title>{{ label(day.date) }}: {{ day.loans }} empréstimos</title>
          </rect>
          <rect
            [attr.x]="75 + i * 71"
            [attr.y]="190 - (day.returns / scale()) * 160"
            width="23"
            [attr.height]="(day.returns / scale()) * 160"
            rx="4"
            fill="#d8c7a0"
          >
            <title>{{ label(day.date) }}: {{ day.returns }} devoluções</title>
          </rect>
          <text [attr.x]="73 + i * 71" y="215" text-anchor="middle">{{ label(day.date) }}</text>
        </g>
      }
    </svg>
    <div class="legend">
      <span><i></i>Empréstimos</span><span><i class="returns"></i>Devoluções</span>
    </div>
    <table class="sr-only">
      <caption>
        Valores do movimento da semana
      </caption>
      <thead>
        <tr>
          <th>Dia</th>
          <th>Empréstimos</th>
          <th>Devoluções</th>
        </tr>
      </thead>
      <tbody>
        @for (day of days(); track day.date) {
          <tr>
            <td>{{ day.date }}</td>
            <td>{{ day.loans }}</td>
            <td>{{ day.returns }}</td>
          </tr>
        }
      </tbody>
    </table>
  `,
  styles: [
    ':host{display:block}svg{width:100%;display:block}text{font:12px sans-serif;fill:#6e746c}.legend{display:flex;justify-content:center;gap:24px;font-size:12px}.legend span{display:flex;align-items:center;gap:8px}i{width:10px;height:10px;border-radius:50%;background:#194c38}i.returns{background:#d8c7a0}.sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%)}',
  ],
})
export class WeeklyMovementComponent {
  readonly days = input<readonly MovementDay[]>([]);
  protected readonly ticks = [0, 0.25, 0.5, 0.75, 1];
  protected readonly scale = computed(() =>
    Math.max(
      4,
      Math.ceil(Math.max(0, ...this.days().flatMap((d) => [d.loans, d.returns])) / 4) * 4,
    ),
  );
  protected readonly rounded = Math.round;
  protected label(date: string): string {
    return new Intl.DateTimeFormat('pt-BR', { weekday: 'short', timeZone: 'UTC' })
      .format(new Date(date + 'T12:00:00Z'))
      .replace('.', '');
  }
}
