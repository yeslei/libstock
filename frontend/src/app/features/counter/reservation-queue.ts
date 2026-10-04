import { AllocationBlock, StaffPurchaseReservation } from './counter.service';

/** Motivos de bloqueio da destinação, conforme `allocation_blocked_reason` devolvido pelo backend. */
export const BLOCK_TEXT: Readonly<Record<AllocationBlock, string>> = {
  NOT_FIRST_IN_QUEUE: 'Aguardando a vez: só a primeira reserva da fila recebe exemplar.',
  CLIENT_INELIGIBLE:
    'O primeiro da fila está inelegível (inativo, penalizado ou em atraso). A destinação fica bloqueada até a situação ser regularizada; o sistema não pula a fila.',
  NO_FREE_COPY: 'Não há exemplar comercial livre para destinar.',
  BOOK_INACTIVE: 'Obra inativa.',
};

export interface ReservationQueue {
  readonly bookId: number;
  readonly title: string;
  readonly entries: readonly StaffPurchaseReservation[];
}

/**
 * Agrupa as reservas por obra, preservando a ordem da consulta. Dentro da obra, a reserva com exemplar
 * destinado vem antes das aguardando, que seguem a posição devolvida pelo backend.
 */
export function groupByBook(reservations: readonly StaffPurchaseReservation[]): ReservationQueue[] {
  const groups = new Map<number, StaffPurchaseReservation[]>();
  for (const reservation of reservations) {
    const entries = groups.get(reservation.book.id) ?? [];
    entries.push(reservation);
    groups.set(reservation.book.id, entries);
  }
  return Array.from(groups.values()).map((entries) => ({
    bookId: entries[0].book.id,
    title: entries[0].book.title,
    entries: [...entries].sort(
      (a, b) =>
        Number(a.status === 'WAITING') - Number(b.status === 'WAITING') ||
        (a.queue_position ?? 0) - (b.queue_position ?? 0) ||
        a.id - b.id,
    ),
  }));
}

/** Há exemplar destinado e nada impede a venda segundo os fatos do backend. */
export function canSellReservation(reservation: StaffPurchaseReservation): boolean {
  return (
    reservation.status === 'NOTIFIED' &&
    reservation.allocated_copy_id !== null &&
    reservation.allocated_copy_barcode !== null &&
    reservation.client.eligible &&
    reservation.book.is_active &&
    !reservation.expired
  );
}
