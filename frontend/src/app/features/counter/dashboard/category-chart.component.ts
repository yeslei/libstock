import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { CategoryCount } from './dashboard.models';
@Component({
  selector: 'app-category-chart',
  standalone: true,
  imports: [],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<div class="chart">
    <div
      class="donut"
      [style.background]="gradient()"
      role="img"
      [attr.aria-label]="total() + ' obras ativas por categoria'"
    >
      <div class="center">
        <strong>{{ total().toLocaleString('pt-BR') }}</strong
        ><span>obras ativas</span>
      </div>
    </div>
    <ul>
      @for (category of categories(); track category.name; let i = $index) {
        <li>
          <div class="category">
            <i [style.background]="color(i)"></i><span>{{ category.name }}</span
            ><strong
              >{{ percent(category.count) }}% <small>({{ category.count }})</small></strong
            >
          </div>
        </li>
      }
    </ul>
  </div>`,
  styles: [
    ':host{display:block}.chart{display:flex;align-items:center;gap:24px;min-height:230px}.donut{width:170px;height:170px;border-radius:50%;padding:28px;flex-shrink:0}.center{background:#fffdf8;width:100%;height:100%;border-radius:50%;display:flex;flex-direction:column;align-items:center;justify-content:center}.center strong{font:700 26px Georgia,serif}.center span{font-size:12px;margin-top:6px}ul{list-style:none;padding:0;margin:0;flex:1;max-height:240px;overflow:auto}li+li{margin-top:14px}.category{display:flex;gap:8px;align-items:center;color:inherit;text-decoration:none;font-size:12px}i{width:10px;height:10px;border-radius:50%;flex-shrink:0}.category span{flex:1}strong{font-weight:500;white-space:nowrap}small{color:#6e746c}@media(max-width:600px){.chart{flex-direction:column}ul{width:100%}}',
  ],
})
export class CategoryChartComponent {
  readonly categories = input<readonly CategoryCount[]>([]);
  protected readonly total = computed(() => this.categories().reduce((sum, c) => sum + c.count, 0));
  protected color(i: number): string {
    return ['#194c38', '#8eaa91', '#edb96f', '#c89c53', '#aaa99a', '#d8c7a0'][i % 6];
  }
  protected percent(count: number): number {
    return this.total() ? Math.round((count / this.total()) * 100) : 0;
  }
  protected readonly gradient = computed(() => {
    let offset = 0;
    return this.total()
      ? 'conic-gradient(' +
          this.categories()
            .map((c, i) => {
              const start = offset;
              offset += (c.count / this.total()) * 100;
              return `${this.color(i)} ${start}% ${offset}%`;
            })
            .join(',') +
          ')'
      : '#e7e1d3';
  });
}
