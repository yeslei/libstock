import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, DestroyRef, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';
import { finalize } from 'rxjs';
import { AlertComponent } from '../../shared/components/alert/alert.component';
import { SpinnerComponent } from '../../shared/components/spinner/spinner.component';
import { ClientNotification, NotificationService } from './notification.service';

@Component({
  selector: 'app-notifications', standalone: true,
  imports: [DatePipe, RouterLink, AlertComponent, SpinnerComponent],
  templateUrl: './notifications.component.html', styleUrl: './notifications.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class NotificationsComponent {
  private readonly api = inject(NotificationService);
  private readonly destroyRef = inject(DestroyRef);
  protected readonly items = signal<readonly ClientNotification[]>([]);
  protected readonly nextBeforeId = signal<number | null>(null);
  protected readonly loading = signal(false);
  protected readonly loaded = signal(false);
  protected readonly reading = signal<number | null>(null);
  protected readonly requiresRefresh = signal(false);
  protected readonly error = signal('');
  protected readonly success = signal('');

  constructor() { this.load(); }

  protected load(more = false): void {
    if (this.loading() || this.reading() !== null || (more && (this.nextBeforeId() === null || this.requiresRefresh()))) return;
    const cursor = more ? this.nextBeforeId() : null;
    if (!more) {
      this.items.set([]); this.nextBeforeId.set(null); this.loaded.set(false);
    }
    this.loading.set(true); this.error.set(''); this.success.set('');
    this.api.list(cursor).pipe(finalize(() => this.loading.set(false)), takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (page) => {
        this.items.update((current) => more ? [...current, ...page.items] : page.items);
        this.nextBeforeId.set(page.next_before_id); this.loaded.set(true); this.requiresRefresh.set(false);
      },
      error: () => this.error.set('Não foi possível consultar suas notificações. Atualize a consulta para continuar.'),
    });
  }

  protected markRead(item: ClientNotification): void {
    if (item.status !== 'SENT' || this.reading() !== null || this.loading() || this.requiresRefresh()) return;
    this.reading.set(item.id); this.error.set(''); this.success.set('');
    this.api.markRead(item.id).pipe(finalize(() => this.reading.set(null)), takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (result) => {
        this.items.update((items) => items.map((current) => current.id === result.id ? result : current));
        this.success.set('Notificação marcada como lida.');
      },
      error: (error) => {
        this.requiresRefresh.set(true);
        this.error.set(!error.status || error.status >= 500
          ? 'Não foi possível confirmar o resultado. Atualize a consulta antes de marcar outra notificação.'
          : typeof error.detail === 'string' ? error.detail : 'Não foi possível atualizar a notificação. Atualize a consulta.');
      },
    });
  }

  protected statusLabel(item: ClientNotification): string {
    if (item.status === 'READ') return 'Lida';
    if (item.status === 'FAILED') return 'Envio não confirmado';
    if (item.status === 'PENDING') return 'Aguardando envio';
    return item.channel === 'IN_APP' ? 'Não lida' : 'Enviado';
  }
}
