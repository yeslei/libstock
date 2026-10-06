import { ChangeDetectionStrategy, Component, input } from '@angular/core';
@Component({
  selector: 'app-stat-card',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template:
    '<div><strong>{{ value() }}</strong><span class="label">{{ label() }}</span><small>{{ note() }}</small></div>',
  styles: [
    ':host{display:block;padding:22px;border:1px solid #e7e1d3;border-radius:16px;background:#fffdf8;text-align:left}strong{font:700 30px Georgia,serif;color:#163126}.label{display:block;font-size:13px;color:#6e746c;margin-top:6px}small{display:block;color:#6e746c;margin-top:10px;font-size:11px}',
  ],
})
export class StatCardComponent {
  readonly value = input('—');
  readonly label = input('');
  readonly note = input('');
}
