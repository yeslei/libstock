import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, signal } from '@angular/core';

import { AlertComponent } from '../../shared/components/alert/alert.component';
import { SpinnerComponent } from '../../shared/components/spinner/spinner.component';
import { ConfirmDialogComponent } from './confirm-dialog.component';
import { DeskPanel } from './desk-panel';
import { StaffLoanRequest } from './counter.service';

@Component({
  selector: 'app-pickups-panel',
  standalone: true,
  imports: [DatePipe, AlertComponent, SpinnerComponent, ConfirmDialogComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './pickups-panel.component.html',
  styleUrl: './desk-panel.scss',
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
    const id = this.selected()[request.id];
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
}
