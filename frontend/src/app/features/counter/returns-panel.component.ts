import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component } from '@angular/core';

import { AlertComponent } from '../../shared/components/alert/alert.component';
import { SpinnerComponent } from '../../shared/components/spinner/spinner.component';
import { ConfirmDialogComponent } from './confirm-dialog.component';
import { DeskPanel } from './desk-panel';
import { StaffLoan } from './counter.service';

@Component({
  selector: 'app-returns-panel',
  standalone: true,
  imports: [DatePipe, AlertComponent, SpinnerComponent, ConfirmDialogComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './returns-panel.component.html',
  styleUrl: './desk-panel.scss',
})
export class ReturnsPanelComponent extends DeskPanel<StaffLoan> {
  protected readonly loadError = 'Não foi possível carregar os empréstimos ativos.';

  protected fetch() {
    return this.service.listLoans({ q: this.term(), clientId: this.client?.id });
  }

  protected confirmReturn(loan: StaffLoan): void {
    this.ask({
      title: 'Confirmar devolução?',
      details: [
        `Cliente: ${loan.client.name} (${loan.client.email})`,
        `Obra: ${loan.book.title}`,
        `Exemplar: ${loan.copy_barcode}`,
        loan.status === 'OVERDUE' ? `Empréstimo em atraso há ${loan.days_late} dia(s).` : 'Empréstimo dentro do prazo.',
      ],
      confirmLabel: 'Confirmar devolução',
      run: () => this.service.confirmReturn(loan.id),
      success: () => `Devolução confirmada: exemplar ${loan.copy_barcode} de “${loan.book.title}”.`,
    });
  }
}
