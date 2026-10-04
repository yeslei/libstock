import { formatDate } from '@angular/common';

import { formatPrice } from '../counter/desk-flow';
import {
  AnyReceipt,
  LoanReceipt,
  ReceiptKind,
  ReceiptPerson,
  ReturnReceipt,
  SaleReceipt,
} from './receipt.service';

export interface ReceiptRow {
  readonly label: string;
  readonly value: string;
}

export interface ReceiptItemRow {
  readonly title: string;
  readonly detail: string;
  readonly price: string;
}

/** Modelo de exibição do comprovante; só formata o que o backend devolveu. */
export interface ReceiptView {
  readonly title: string;
  readonly number: number;
  readonly rows: readonly ReceiptRow[];
  readonly items: readonly ReceiptItemRow[];
  readonly total: string | null;
}

// Formatos numéricos: independem do idioma, então não exige o registro do locale pt-BR.
const LOCALE = 'en-US';
/** America/Sao_Paulo (sem horário de verão desde 2019), o mesmo deslocamento usado nas telas do balcão. */
const ZONE = '-0300';

const day = (value: string) => formatDate(value, 'dd/MM/yyyy', LOCALE, ZONE);
const moment = (value: string) => formatDate(value, 'dd/MM/yyyy HH:mm', LOCALE, ZONE);

function person(value: ReceiptPerson): string {
  return value.code ? `${value.name} (${value.code})` : value.name;
}

function loanRows(receipt: LoanReceipt): ReceiptRow[] {
  const author = receipt.book.author ? ` — ${receipt.book.author}` : '';
  return [
    { label: 'Cliente', value: person(receipt.client) },
    { label: 'Obra', value: `${receipt.book.title}${author}` },
    { label: 'Exemplar', value: receipt.copy_barcode },
    { label: 'Data do empréstimo', value: moment(receipt.loan_date) },
    { label: 'Devolução prevista', value: day(receipt.due_date) },
    { label: 'Funcionário responsável', value: person(receipt.employee) },
  ];
}

function lateness(days: number): string {
  if (days <= 0) return 'Devolvido no prazo';
  return `${days} ${days === 1 ? 'dia' : 'dias'} de atraso`;
}

export function toReceiptView(kind: ReceiptKind, receipt: AnyReceipt): ReceiptView {
  if (kind === 'sale') {
    const sale = receipt as SaleReceipt;
    return {
      title: 'Comprovante de venda',
      number: sale.number,
      rows: [
        { label: 'Data da venda', value: moment(sale.sale_date) },
        { label: 'Cliente', value: sale.client ? person(sale.client) : 'Venda sem cliente identificado' },
        { label: 'Funcionário responsável', value: person(sale.employee) },
      ],
      items: sale.items.map((item) => ({
        title: item.book.author ? `${item.book.title} — ${item.book.author}` : item.book.title,
        detail: `Exemplar ${item.copy_barcode}`,
        price: formatPrice(item.unit_price),
      })),
      total: formatPrice(sale.total_amount),
    };
  }
  if (kind === 'return') {
    const returned = receipt as ReturnReceipt;
    return {
      title: 'Comprovante de devolução',
      number: returned.number,
      rows: [
        ...loanRows(returned),
        { label: 'Devolvido em', value: moment(returned.returned_at) },
        { label: 'Situação da devolução', value: lateness(returned.days_late) },
      ],
      items: [],
      total: null,
    };
  }
  const loan = receipt as LoanReceipt;
  return { title: 'Comprovante de empréstimo', number: loan.number, rows: loanRows(loan), items: [], total: null };
}
