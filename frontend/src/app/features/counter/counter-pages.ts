import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { Router } from '@angular/router';

import { ClientNavigation, ClientsPanelComponent, DeskTab } from './clients-panel.component';
import { CounterContext } from './counter-context.service';
import { PickupsPanelComponent } from './pickups-panel.component';
import { ReservationsPanelComponent } from './reservations-panel.component';

/** Destino de cada atalho da consulta de clientes dentro da área do funcionário. */
const DESTINATIONS: Readonly<Record<DeskTab, string>> = {
  retiradas: '/balcao/emprestimos/solicitacoes',
  devolucoes: '/balcao/emprestimos/ativos',
  reservas: '/balcao/reservas',
};

@Component({
  selector: 'app-counter-clients-page',
  standalone: true,
  imports: [ClientsPanelComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<app-clients-panel (open)="open($event)" />`,
})
export class CounterClientsPageComponent {
  private readonly context = inject(CounterContext);
  private readonly router = inject(Router);

  protected open(navigation: ClientNavigation): void {
    this.context.client.set(navigation.client);
    void this.router.navigateByUrl(DESTINATIONS[navigation.tab]);
  }
}

@Component({
  selector: 'app-counter-pickups-page',
  standalone: true,
  imports: [PickupsPanelComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<app-pickups-panel [client]="context.client()" (clearClient)="context.client.set(null)" />`,
})
export class CounterPickupsPageComponent {
  protected readonly context = inject(CounterContext);
}

@Component({
  selector: 'app-counter-reservations-page',
  standalone: true,
  imports: [ReservationsPanelComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<app-reservations-panel [client]="context.client()" (clearClient)="context.client.set(null)" />`,
})
export class CounterReservationsPageComponent {
  protected readonly context = inject(CounterContext);
}
