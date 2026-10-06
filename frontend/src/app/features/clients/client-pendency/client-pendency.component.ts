import { ChangeDetectionStrategy, Component, DestroyRef, OnInit, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';

import { ApiError } from '../../../core/models/auth.model';
import { AlertComponent } from '../../../shared/components/alert/alert.component';
import { SpinnerComponent } from '../../../shared/components/spinner/spinner.component';
import { ClientPendencyService } from '../services/client-pendency.service';
import { ClientPendency, PenaltyAction } from '../models/client-pendency.model';

@Component({
  selector: 'app-client-pendency',
  standalone: true,
  imports: [FormsModule, DatePipe, AlertComponent, SpinnerComponent],
  templateUrl: './client-pendency.component.html',
  styleUrl: './client-pendency.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ClientPendencyComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly api = inject(ClientPendencyService);
  private readonly destroyRef = inject(DestroyRef);

  protected readonly data = signal<ClientPendency | null>(null);
  protected readonly loading = signal(true);
  protected readonly saving = signal(false);
  protected readonly modalOpen = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly success = signal<string | null>(null);
  protected reason = '';
  protected action: PenaltyAction = 'APPLY';
  protected clientId = 0;

  ngOnInit(): void {
    this.clientId = Number(this.route.snapshot.paramMap.get('id'));
    this.load();
  }

  protected openPenaltyDialog(): void {
    const current = this.data();
    if (!current) return;
    this.action = current.is_penalized ? 'REMOVE' : 'APPLY';
    this.reason = '';
    this.error.set(null);
    this.modalOpen.set(true);
  }

  protected closePenaltyDialog(): void {
    if (!this.saving()) this.modalOpen.set(false);
  }

  protected savePenalty(): void {
    const reason = this.reason.trim();
    if (reason.length < 3) {
      this.error.set('Informe um motivo com pelo menos 3 caracteres.');
      return;
    }
    this.saving.set(true);
    this.error.set(null);
    this.success.set(null);
    this.api.updatePenalty(this.clientId, { action: this.action, reason })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (data) => {
          this.data.set(data);
          this.modalOpen.set(false);
          this.saving.set(false);
          this.success.set('Situação de penalidade atualizada com sucesso.');
        },
        error: (error: ApiError) => {
          this.saving.set(false);
          this.error.set(error.detail || 'Não foi possível alterar a penalidade.');
        },
      });
  }

  private load(): void {
    this.api.get(this.clientId).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (data) => { this.data.set(data); this.loading.set(false); },
      error: (error: ApiError) => {
        this.error.set(error.detail || 'Não foi possível carregar as pendências.');
        this.loading.set(false);
      },
    });
  }
}
