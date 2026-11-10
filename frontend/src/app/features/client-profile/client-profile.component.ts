import { ChangeDetectionStrategy, Component, DestroyRef, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { finalize } from 'rxjs';
import { AlertComponent } from '../../shared/components/alert/alert.component';
import { SpinnerComponent } from '../../shared/components/spinner/spinner.component';
import { NotificationChannel, NotificationPreference, NotificationPreferenceService } from './notification-preference.service';

@Component({
  selector: 'app-client-profile', standalone: true,
  imports: [FormsModule, RouterLink, AlertComponent, SpinnerComponent],
  templateUrl: './client-profile.component.html', styleUrl: './client-profile.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ClientProfileComponent {
  private readonly api = inject(NotificationPreferenceService);
  private readonly destroyRef = inject(DestroyRef);
  protected readonly preference = signal<NotificationPreference | null>(null);
  protected readonly loading = signal(false);
  protected readonly saving = signal(false);
  protected readonly uncertain = signal(false);
  protected readonly error = signal('');
  protected readonly success = signal('');
  protected channel: NotificationChannel = 'IN_APP';

  constructor() { this.load(); }

  protected load(): void {
    if (this.loading() || this.saving()) return;
    this.loading.set(true); this.error.set(''); this.success.set('');
    this.api.get().pipe(finalize(() => this.loading.set(false)), takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (data) => { this.preference.set(data); this.channel = data.channel; this.uncertain.set(false); },
      error: () => this.error.set('Não foi possível consultar suas preferências. Atualize a consulta para continuar.'),
    });
  }

  protected save(): void {
    if (this.saving() || this.loading() || this.uncertain() || !this.preference() || this.channel === this.preference()?.channel) return;
    this.saving.set(true); this.error.set(''); this.success.set('');
    this.api.update(this.channel).pipe(finalize(() => this.saving.set(false)), takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (data) => { this.preference.set(data); this.channel = data.channel; this.success.set('Preferência de notificação salva.'); },
      error: (error) => {
        if (!error.status || error.status >= 500) {
          this.uncertain.set(true);
          this.error.set('Não foi possível confirmar o resultado. Atualize a consulta antes de alterar novamente.');
        } else {
          this.error.set(typeof error.detail === 'string' ? error.detail : 'Não foi possível salvar a preferência de notificação.');
        }
      },
    });
  }
}
