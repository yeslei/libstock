import { ChangeDetectionStrategy, Component, signal } from '@angular/core';

import { ClientNavigation, ClientsPanelComponent } from './clients-panel.component';
import { StaffClient } from './counter.service';
import { PickupsPanelComponent } from './pickups-panel.component';
import { ReservationsPanelComponent } from './reservations-panel.component';
import { ReturnsPanelComponent } from './returns-panel.component';

type Tab = 'clientes' | 'retiradas' | 'devolucoes' | 'reservas';

const TABS: readonly { readonly id: Tab; readonly label: string }[] = [
  { id: 'clientes', label: 'Clientes' },
  { id: 'retiradas', label: 'Retiradas' },
  { id: 'devolucoes', label: 'Devoluções' },
  { id: 'reservas', label: 'Reservas de compra' },
];

/** Área operacional de balcão (V2). Acesso restrito a SELLER e ADMINISTRATOR pela rota. */
@Component({
  selector: 'app-counter',
  standalone: true,
  imports: [ClientsPanelComponent, PickupsPanelComponent, ReturnsPanelComponent, ReservationsPanelComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './counter.component.html',
  styleUrl: './counter.component.scss',
})
export class CounterComponent {
  protected readonly tabs = TABS;
  protected readonly tab = signal<Tab>('clientes');
  protected readonly client = signal<StaffClient | null>(null);

  protected select(tab: Tab): void {
    this.tab.set(tab);
  }

  protected openClient(navigation: ClientNavigation): void {
    this.client.set(navigation.client);
    this.tab.set(navigation.tab);
  }

  protected clearClient(): void {
    this.client.set(null);
  }

  protected moveFocus(event: KeyboardEvent, index: number): void {
    const keys: Record<string, number> = { ArrowRight: 1, ArrowLeft: -1, Home: -index, End: TABS.length - 1 - index };
    if (!(event.key in keys)) return;
    event.preventDefault();
    const next = (index + keys[event.key] + TABS.length) % TABS.length;
    this.select(TABS[next].id);
    queueMicrotask(() => document.getElementById('tab-' + TABS[next].id)?.focus());
  }
}
