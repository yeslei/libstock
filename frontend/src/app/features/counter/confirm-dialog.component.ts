import {
  AfterViewInit,
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  EventEmitter,
  Input,
  OnDestroy,
  Output,
  viewChild,
} from '@angular/core';

import { SpinnerComponent } from '../../shared/components/spinner/spinner.component';

let nextId = 0;

/** Diálogo modal nativo: foco preso, Esc cancela e o fundo fica inerte. */
@Component({
  selector: 'app-confirm-dialog',
  standalone: true,
  imports: [SpinnerComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <dialog
      #dialog
      class="confirm"
      [attr.aria-labelledby]="id + '-title'"
      [attr.aria-describedby]="id + '-details'"
      (cancel)="onEscape($event)"
    >
      <h2 [id]="id + '-title'">{{ title }}</h2>
      @if (intro) {
        <p class="confirm__intro">{{ intro }}</p>
      }
      @if (detailsTitle) {
        <h3 class="confirm__details-title">{{ detailsTitle }}</h3>
      }
      <ul class="confirm__details" [id]="id + '-details'">
        @for (line of details; track line) {
          <li>{{ line }}</li>
        }
      </ul>
      <div class="confirm__actions">
        <button type="button" class="confirm__cancel" [disabled]="busy" (click)="cancelled.emit()">
          Cancelar
        </button>
        <button
          type="button"
          class="confirm__submit"
          [disabled]="busy"
          [attr.aria-busy]="busy"
          (click)="confirmed.emit()"
        >
          @if (busy) {
            <app-spinner [size]="16" />
            <span>Confirmando…</span>
          } @else {
            <span>{{ confirmLabel }}</span>
          }
        </button>
      </div>
    </dialog>
  `,
  styleUrl: './confirm-dialog.component.scss',
})
export class ConfirmDialogComponent implements AfterViewInit, OnDestroy {
  @Input({ required: true }) title = '';
  @Input() intro = '';
  @Input() detailsTitle = '';
  @Input() details: readonly string[] = [];
  @Input() confirmLabel = 'Confirmar';
  @Input() busy = false;
  @Output() readonly confirmed = new EventEmitter<void>();
  @Output() readonly cancelled = new EventEmitter<void>();

  protected readonly id = `confirm-${nextId++}`;
  private readonly dialog = viewChild.required<ElementRef<HTMLDialogElement>>('dialog');

  ngAfterViewInit(): void {
    const element = this.dialog().nativeElement;
    if (typeof element.showModal === 'function') element.showModal();
    else element.setAttribute('open', '');
  }

  ngOnDestroy(): void {
    const element = this.dialog().nativeElement;
    if (element.open && typeof element.close === 'function') element.close();
  }

  protected onEscape(event: Event): void {
    event.preventDefault();
    if (!this.busy) this.cancelled.emit();
  }
}
