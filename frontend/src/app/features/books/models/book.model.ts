export type CopyDestination = 'DIDACTIC' | 'COMMERCIAL';
export type CopyStatus = 'AVAILABLE';

export interface InitialCopyCreateRequest {
  readonly barcode: string;
  readonly destination: CopyDestination;
  readonly condition: string | null;
  readonly sale_price: number | null;
  readonly acquired_at: string | null;
}

export interface BookCreateRequest {
  readonly isbn: string;
  readonly title: string | null;
  readonly author: string | null;
  readonly genre: string | null;
  readonly initial_copy: InitialCopyCreateRequest;
}

export interface CopyResponse extends Omit<InitialCopyCreateRequest, 'sale_price'> {
  readonly id: number;
  readonly book_id: number;
  readonly is_active: boolean;
  readonly status: CopyStatus;
  readonly sale_price: number | string | null;
}

/** Espelha o contrato persistido de `BookResponse`. */
export interface BookResponse {
  readonly id: number;
  readonly isbn: string | null;
  readonly title: string;
  readonly author: string;
  readonly genre: string | null;
  readonly is_active: boolean;
  readonly initial_copy: CopyResponse | null;
}
