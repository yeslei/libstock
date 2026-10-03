import { Injectable, signal } from '@angular/core';

import { StaffClient } from './counter.service';

/** Cliente escolhido em "Clientes" para filtrar as demais telas do balcão (estado de navegação, sem persistência). */
@Injectable({ providedIn: 'root' })
export class CounterContext {
  readonly client = signal<StaffClient | null>(null);
}
