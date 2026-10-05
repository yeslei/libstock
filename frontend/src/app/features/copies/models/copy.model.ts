export type DestinationType = 'COMMERCIAL' | 'DIDACTIC';

export interface CopyCreateRequest {
  readonly bookId: number;
  readonly barcode: string;
  readonly destination: DestinationType;
  readonly condition: string | null;
  readonly salePrice: number | null;
  readonly acquiredAt: string | null;
}

/** Corpo de `PATCH /api/v1/copies/{id}`; o código do exemplar é imutável e não faz parte da edição. */
export interface CopyUpdateRequest {
  readonly isActive?: boolean;
  readonly destination?: DestinationType;
  readonly condition?: string | null;
  readonly salePrice?: number | null;
  readonly acquiredAt?: string | null;
}

export type CopyStatus = 'AVAILABLE' | 'BORROWED' | 'SOLD' | 'RESERVED' | 'INACTIVE';

export interface CopyResponse {
  readonly id: number;
  readonly bookId: number;
  readonly barcode: string;
  readonly destination: DestinationType;
  readonly condition: string | null;
  readonly salePrice: number | null;
  readonly acquiredAt: string | null;
  readonly status: CopyStatus;
  readonly isActive: boolean;
}

interface CopyResponseApi {
  readonly id: number;
  readonly book_id: number;
  readonly barcode: string;
  readonly destination: DestinationType;
  readonly condition: string | null;
  readonly sale_price: number | null;
  readonly acquired_at: string | null;
  readonly status: CopyStatus;
  readonly is_active: boolean;
}

export function copyResponseFromApi(copy: CopyResponseApi): CopyResponse {
  return {
    id: copy.id,
    bookId: copy.book_id,
    barcode: copy.barcode,
    destination: copy.destination,
    condition: copy.condition,
    salePrice: copy.sale_price,
    acquiredAt: copy.acquired_at,
    status: copy.status,
    isActive: copy.is_active,
  };
}

/** Resposta de `DELETE /api/v1/copies/{id}`: o exemplar removido. */
export interface CopyDeleteResult {
  readonly id: number;
  readonly bookId: number;
  readonly barcode: string;
}

export function copyDeleteResultFromApi(result: { id: number; book_id: number; barcode: string }): CopyDeleteResult {
  return { id: result.id, bookId: result.book_id, barcode: result.barcode };
}
