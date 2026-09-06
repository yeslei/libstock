import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  ElementRef,
  inject,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormBuilder, ReactiveFormsModule, ValidationErrors, ValidatorFn, Validators } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';

import { ApiError } from '../../../core/models/auth.model';
import { AlertComponent } from '../../../shared/components/alert/alert.component';
import { SpinnerComponent } from '../../../shared/components/spinner/spinner.component';
import { fieldError } from '../../../shared/validators/form-errors';
import { CopyCreateRequest, CopyResponse, DestinationType } from '../models/copy.model';
import { CopyService } from '../services/copy.service';

type CopyCreateState = 'idle' | 'submitting' | 'success' | 'error' | 'invalidRoute';

const BARCODE_ERRORS = {
  required: 'Informe o código de barras.',
  maxlength: 'O código de barras pode ter no máximo 100 caracteres.',
  server: 'Confira o código de barras informado.',
};
const DESTINATION_ERRORS = { required: 'Escolha a destinação do exemplar.', server: 'Confira a destinação.' };
const CONDITION_ERRORS = { maxlength: 'A condição pode ter no máximo 30 caracteres.', server: 'Confira a condição.' };
const PRICE_ERRORS = {
  required: 'Informe o preço de venda.',
  price: 'Informe um preço não negativo, com até 10 dígitos e duas casas decimais.',
  server: 'Confira o preço de venda.',
};

const salePriceValidator: ValidatorFn = (control): ValidationErrors | null => {
  const value = String(control.value ?? '');
  if (!value) {
    return null;
  }
  if (!/^\d+(?:\.\d{1,2})?$/.test(value) || value.replace('.', '').length > 10) {
    return { price: true };
  }
  return null;
};

@Component({
  selector: 'app-copy-create',
  standalone: true,
  imports: [ReactiveFormsModule, RouterLink, AlertComponent, SpinnerComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './copy-create.component.html',
  styleUrl: './copy-create.component.scss',
})
export class CopyCreateComponent {
  private readonly fb = inject(FormBuilder);
  private readonly route = inject(ActivatedRoute);
  private readonly copies = inject(CopyService);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  private readonly destroyRef = inject(DestroyRef);

  protected readonly form = this.fb.nonNullable.group({
    barcode: ['', [Validators.required, Validators.maxLength(100)]],
    destination: ['', [Validators.required]],
    condition: ['', [Validators.maxLength(30)]],
    salePrice: [''],
    acquiredAt: [''],
  });
  protected readonly state = signal<CopyCreateState>('idle');
  protected readonly message = signal<string | null>(null);
  protected readonly submitted = signal(false);
  protected readonly createdCopy = signal<CopyResponse | null>(null);
  private readonly bookId = signal<number | null>(null);

  constructor() {
    this.route.paramMap.pipe(takeUntilDestroyed(this.destroyRef)).subscribe((params) => {
      const id = Number(params.get('id'));
      if (!Number.isSafeInteger(id) || id <= 0) {
        this.bookId.set(null);
        this.state.set('invalidRoute');
        this.message.set('O identificador da obra é inválido.');
        return;
      }
      this.bookId.set(id);
      if (this.state() === 'invalidRoute') {
        this.state.set('idle');
        this.message.set(null);
      }
    });

    this.form.controls.destination.valueChanges
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe((destination) => this.updatePriceValidators(destination));
  }

  protected get isSubmitting(): boolean {
    return this.state() === 'submitting';
  }

  protected get formError(): string | null {
    return this.state() === 'error' || this.state() === 'invalidRoute' ? this.message() : null;
  }

  protected barcodeError(): string | null {
    return fieldError(this.form.controls.barcode, BARCODE_ERRORS, this.submitted());
  }

  protected destinationError(): string | null {
    return fieldError(this.form.controls.destination, DESTINATION_ERRORS, this.submitted());
  }

  protected conditionError(): string | null {
    return fieldError(this.form.controls.condition, CONDITION_ERRORS, this.submitted());
  }

  protected salePriceError(): string | null {
    return fieldError(this.form.controls.salePrice, PRICE_ERRORS, this.submitted());
  }

  protected submit(): void {
    if (this.isSubmitting || this.bookId() === null) {
      return;
    }
    this.submitted.set(true);
    if (this.form.invalid) {
      this.state.set('idle');
      this.message.set(null);
      this.focusFirstInvalid();
      return;
    }

    this.state.set('submitting');
    this.message.set(null);
    this.copies
      .create(this.payload())
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (copy) => {
          this.createdCopy.set(copy);
          this.state.set('success');
        },
        error: (error: ApiError) => this.handleError(error),
      });
  }

  protected registerAnother(): void {
    this.form.reset({ barcode: '', destination: '', condition: '', salePrice: '', acquiredAt: '' });
    this.updatePriceValidators('');
    this.createdCopy.set(null);
    this.submitted.set(false);
    this.message.set(null);
    this.state.set('idle');
    this.focus('copy-barcode');
  }

  private updatePriceValidators(destination: string): void {
    const validators = destination === 'COMMERCIAL' ? [Validators.required, salePriceValidator] : [];
    this.form.controls.salePrice.setValidators(validators);
    this.form.controls.salePrice.updateValueAndValidity({ emitEvent: false });
  }

  private payload(): CopyCreateRequest {
    const value = this.form.getRawValue();
    const destination = value.destination as DestinationType;
    return {
      bookId: this.bookId()!,
      barcode: value.barcode.trim(),
      destination,
      condition: value.condition.trim() || null,
      salePrice: destination === 'COMMERCIAL' ? Number(value.salePrice) : null,
      acquiredAt: value.acquiredAt || null,
    };
  }

  private handleError(error: ApiError): void {
    if (error.status === 422 && this.applyValidationErrors(error)) {
      this.state.set('error');
      this.message.set('Confira os campos destacados e tente novamente.');
      this.focusFirstInvalid();
      return;
    }
    if (error.status === 409) {
      this.state.set('error');
      this.message.set('Este código de barras já está cadastrado.');
      this.focus('copy-barcode');
      return;
    }
    if (error.status === 404) {
      this.state.set('error');
      this.message.set('A obra não foi encontrada ou não está ativa.');
      return;
    }
    this.state.set('error');
    this.message.set(error.detail);
  }

  private applyValidationErrors(error: ApiError): boolean {
    const fields: Record<string, keyof typeof this.form.controls> = {
      barcode: 'barcode',
      destination: 'destination',
      condition: 'condition',
      sale_price: 'salePrice',
      acquired_at: 'acquiredAt',
    };
    let applied = false;
    for (const issue of error.validationErrors ?? []) {
      const field = issue.field ? fields[issue.field] : undefined;
      if (field) {
        const control = this.form.controls[field];
        control.setErrors({ ...(control.errors ?? {}), server: true });
        control.markAsTouched();
        applied = true;
      }
    }
    return applied;
  }

  private focusFirstInvalid(): void {
    const first = (['barcode', 'destination', 'condition', 'salePrice', 'acquiredAt'] as const).find(
      (field) => this.form.controls[field].invalid,
    );
    if (first) {
      this.focus(`copy-${first}`);
    }
  }

  private focus(id: string): void {
    this.host.nativeElement.querySelector<HTMLElement>(`#${id}`)?.focus();
  }
}
