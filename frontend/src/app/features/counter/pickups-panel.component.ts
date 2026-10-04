import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { AlertComponent } from '../../shared/components/alert/alert.component';
import { SpinnerComponent } from '../../shared/components/spinner/spinner.component';
import { SaveFailureComponent } from './save-failure.component';
import { ConfirmDialogComponent } from './confirm-dialog.component';
import { businessToday } from './business-date';
import { DeskPanel } from './desk-panel';
import { StaffLoanRequest } from './counter.service';

@Component({
  selector: 'app-pickups-panel',
  standalone: true,
  imports: [SaveFailureComponent, DatePipe, RouterLink, AlertComponent, SpinnerComponent, ConfirmDialogComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './pickups-panel.component.html',
  styleUrl: './pickups-panel.component.scss',
})
export class PickupsPanelComponent extends DeskPanel<StaffLoanRequest> {
  protected readonly loadError = 'Não foi possível carregar as solicitações de empréstimo.';
  protected readonly selected = signal<Readonly<Record<number, number>>>({});

  protected fetch() {
    return this.service.listLoanRequests({ q: this.term(), clientId: this.client?.id });
  }

  protected selectCopy(request: StaffLoanRequest, event: Event): void {
    const value = Number((event.target as HTMLSelectElement).value);
    this.selected.update((current) => ({ ...current, [request.id]: value }));
  }

  protected copyFor(request: StaffLoanRequest) {
    // Com um único exemplar elegível não há o que escolher: ele já é o exemplar da retirada.
    const id = this.selected()[request.id] ?? (request.eligible_copies.length === 1 ? request.eligible_copies[0].id : undefined);
    return request.eligible_copies.find((copy) => copy.id === id) ?? null;
  }

  protected canConfirm(request: StaffLoanRequest): boolean {
    return request.client.eligible && request.book.is_active && this.copyFor(request) !== null && !this.submitting();
  }

  protected confirmPickup(request: StaffLoanRequest): void {
    const copy = this.copyFor(request);
    if (!copy || !this.canConfirm(request)) return;
    this.ask({
      title: 'Confirmar retirada?',
      details: [
        `Cliente: ${request.client.name} (${request.client.email})`,
        `Obra: ${request.book.title}`,
        `Exemplar didático: ${copy.barcode}`,
        'O empréstimo será registrado agora; o prazo de devolução é calculado pelo sistema.',
      ],
      confirmLabel: 'Confirmar retirada',
      run: () => this.service.confirmPickup(request.id, copy.id),
      success: (result) => `Retirada confirmada. Empréstimo #${result.id} registrado para ${request.client.name}.`,
    });
  }

  protected pendencyLabel(request: StaffLoanRequest): string {
    if (request.client.eligible) return 'Sem pendências';
    const reasons = this.ineligibleReasons(request.client).join(', ');
    return reasons.charAt(0).toUpperCase() + reasons.slice(1);
  }

  /** Retiradas previstas para hoje (calendário de São Paulo) primeiro; as demais pendentes ficam em seção própria. */
  protected groups(requests: readonly StaffLoanRequest[]) {
    const today = businessToday();
    const result = [
      { title: 'RETIRADAS DE HOJE', items: requests.filter((r) => r.pickup_date === today) },
      { title: 'OUTRAS SOLICITAÇÕES', items: requests.filter((r) => r.pickup_date !== today) },
    ];
    return result.filter((group) => group.items.length > 0);
  }
}
