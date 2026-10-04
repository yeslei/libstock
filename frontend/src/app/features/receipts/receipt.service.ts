import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

export type ReceiptKind = 'loan' | 'return' | 'sale';

export interface ReceiptPerson {
  readonly id: number;
  readonly name: string;
  readonly code: string | null;
}

export interface ReceiptBook {
  readonly title: string;
  readonly author: string;
  readonly isbn: string | null;
}

/** `GET /api/v1/receipts/loans/{id}`: dados persistidos do empréstimo. */
export interface LoanReceipt {
  readonly number: number;
  readonly client: ReceiptPerson;
  readonly employee: ReceiptPerson;
  readonly book: ReceiptBook;
  readonly copy_id: number;
  readonly copy_barcode: string;
  readonly loan_date: string;
  readonly due_date: string;
}

/** `GET /api/v1/receipts/returns/{loan_id}`: o empréstimo e a devolução gravada. */
export interface ReturnReceipt extends LoanReceipt {
  readonly returned_at: string;
  readonly days_late: number;
}

export interface SaleReceiptItem {
  readonly copy_id: number;
  readonly copy_barcode: string;
  readonly book: ReceiptBook;
  /** Decimal serializado como texto. */
  readonly unit_price: string | number;
}

/** `GET /api/v1/receipts/sales/{id}`: somente vendas confirmadas. */
export interface SaleReceipt {
  readonly number: number;
  readonly client: ReceiptPerson | null;
  readonly employee: ReceiptPerson;
  readonly sale_date: string;
  readonly items: readonly SaleReceiptItem[];
  readonly total_amount: string | number;
}

export type AnyReceipt = LoanReceipt | ReturnReceipt | SaleReceipt;

const BASE = '/api/v1/receipts';

/** Consultas somente leitura dos comprovantes: nada é calculado nem gravado no frontend. */
@Injectable({ providedIn: 'root' })
export class ReceiptService {
  private readonly http = inject(HttpClient);

  getLoan(loanId: number): Observable<LoanReceipt> {
    return this.http.get<LoanReceipt>(`${BASE}/loans/${loanId}`);
  }

  getReturn(loanId: number): Observable<ReturnReceipt> {
    return this.http.get<ReturnReceipt>(`${BASE}/returns/${loanId}`);
  }

  getSale(saleId: number): Observable<SaleReceipt> {
    return this.http.get<SaleReceipt>(`${BASE}/sales/${saleId}`);
  }

  get(kind: ReceiptKind, id: number): Observable<AnyReceipt> {
    switch (kind) {
      case 'loan':
        return this.getLoan(id);
      case 'return':
        return this.getReturn(id);
      default:
        return this.getSale(id);
    }
  }
}

/** Caminho da rota dedicada de cada comprovante (guard: funcionário ou dono). */
export function receiptPath(kind: ReceiptKind, id: number): string {
  const segment = kind === 'loan' ? 'emprestimo' : kind === 'return' ? 'devolucao' : 'venda';
  return `/comprovantes/${segment}/${id}`;
}
