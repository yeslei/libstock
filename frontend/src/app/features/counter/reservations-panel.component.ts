import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, signal } from '@angular/core';

import { AlertComponent } from '../../shared/components/alert/alert.component';
import { SpinnerComponent } from '../../shared/components/spinner/spinner.component';
import { ConfirmDialogComponent } from './confirm-dialog.component';
import { DeskPanel } from './desk-panel';
import { AllocationBlock, ReservationStatus, StaffPurchaseReservation } from './counter.service';

const BLOCK_TEXT: Readonly<Record<AllocationBlock, string>> = {
  NOT_FIRST_IN_QUEUE: 'Aguardando a vez: só a primeira reserva da fila recebe exemplar.',
  CLIENT_INELIGIBLE:
    'O primeiro da fila está inelegível (inativo, penalizado ou em atraso). A destinação fica bloqueada até a situação ser regularizada; o sistema não pula a fila.',
  NO_FREE_COPY: 'Não há exemplar comercial livre para destinar.',
  BOOK_INACTIVE: 'Obra inativa.',
};

@Component({
  selector: 'app-reservations-panel',
  standalone: true,
  imports: [DatePipe, AlertComponent, SpinnerComponent, ConfirmDialogComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './reservations-panel.component.html',
  styleUrl: './desk-panel.scss',
})
export class ReservationsPanelComponent extends DeskPanel<StaffPurchaseReservation> {
  protected readonly loadError = 'Não foi possível carregar as reservas de compra.';
  protected readonly status = signal<ReservationStatus | ''>('');

  protected fetch() {
    return this.service.listPurchaseReservations({
      q: this.term(),
      clientId: this.client?.id,
      status: this.status(),
    });
  }

  protected setStatus(event: Event): void {
    this.status.set((event.target as HTMLSelectElement).value as ReservationStatus | '');
    this.reload();
  }

  protected blockText(reservation: StaffPurchaseReservation): string | null {
    return reservation.allocation_blocked_reason ? BLOCK_TEXT[reservation.allocation_blocked_reason] : null;
  }

  protected allocate(reservation: StaffPurchaseReservation): void {
    if (!reservation.can_allocate) return;
    this.ask({
      title: 'Destinar exemplar?',
      details: [
        `Obra: ${reservation.book.title}`,
        `Primeiro da fila: ${reservation.client.name} (${reservation.client.email})`,
        `Exemplares comerciais livres: ${reservation.free_commercial_copies}`,
        'Um exemplar comercial livre ficará destinado a este cliente e indisponível para outros.',
      ],
      confirmLabel: 'Destinar exemplar',
      run: () => this.service.allocatePurchase(reservation.book.id),
      success: () => `Exemplar destinado a ${reservation.client.name} para “${reservation.book.title}”.`,
    });
  }

  protected canSell(reservation: StaffPurchaseReservation): boolean {
    return (
      reservation.status === 'NOTIFIED' &&
      reservation.allocated_copy_id !== null &&
      !reservation.expired &&
      !this.submitting()
    );
  }

  protected confirmSale(reservation: StaffPurchaseReservation): void {
    if (!this.canSell(reservation)) return;
    this.ask({
      title: 'Confirmar venda?',
      details: [
        `Cliente: ${reservation.client.name} (${reservation.client.email})`,
        `Obra: ${reservation.book.title}`,
        `Exemplar destinado: ${reservation.allocated_copy_barcode}`,
        'A venda será registrada agora e o exemplar sairá do estoque.',
      ],
      confirmLabel: 'Confirmar venda',
      run: () => this.service.confirmSale(reservation.id),
      success: (result) => `Venda #${result.id} confirmada para ${reservation.client.name}.`,
    });
  }
}
