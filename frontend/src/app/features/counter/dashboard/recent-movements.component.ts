import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { RouterLink } from '@angular/router';
import { RecentMovement } from './dashboard.models';
@Component({
  selector: 'app-recent-movements',
  standalone: true,
  imports: [RouterLink, DatePipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<div class="scroll">
    <table>
      <thead>
        <tr>
          <th>Livro</th>
          <th>Cliente</th>
          <th>Data</th>
          @if (!returns()) {
            <th>Devolução</th>
          }
          <th>Status</th>
        </tr>
      </thead>
      <tbody>
        @for (item of items(); track item.id) {
          <tr>
            <td>
              <a [routerLink]="['/balcao/acervo', item.book_id]">{{ item.title }}</a>
            </td>
            <td>{{ item.client }}</td>
            <td>{{ (returns() ? item.returned_at : item.date) | date: 'dd/MM' : '-0300' }}</td>
            @if (!returns()) {
              <td>{{ item.due_date | date: 'dd/MM' : '-0300' }}</td>
            }
            <td>
              <span class="status" [class.returned]="item.status === 'RETURNED'">{{
                item.status === 'RETURNED' ? 'Devolvido' : 'Ativo'
              }}</span>
            </td>
          </tr>
        } @empty {
          <tr>
            <td [attr.colspan]="returns() ? 4 : 5">Nenhuma movimentação registrada.</td>
          </tr>
        }
      </tbody>
    </table>
  </div>`,
  styles: [
    ':host{display:block}.scroll{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:12px}th{text-align:left;color:#6e746c;font-weight:500;padding:12px 10px;border-bottom:1px solid #e7e1d3}td{padding:16px 10px;border-bottom:1px solid #f1ede5}a{color:#163126;text-decoration:none;font-weight:600}a:hover{text-decoration:underline}.status{display:inline-block;border-radius:20px;padding:5px 9px;background:#e7f0e4;color:#194c38;white-space:nowrap}.returned{background:#edf0eb;color:#657263}',
  ],
})
export class RecentMovementsComponent {
  readonly items = input<readonly RecentMovement[]>([]);
  readonly returns = input(false);
}
