export type CopyDestination = 'DIDACTIC' | 'COMMERCIAL';
export type CopyStatus = 'AVAILABLE' | 'BORROWED' | 'SOLD' | 'RESERVED' | 'INACTIVE';

export interface InitialCopyCreateRequest {
  readonly barcode: string;
  readonly destination: CopyDestination;
  readonly condition: string | null;
  readonly sale_price: number | null;
  readonly acquired_at: string | null;
}

/** Categoria do catálogo público (`genres`). */
export interface BookGenre {
  readonly id: number;
  readonly name: string;
  readonly slug: string;
}

export interface BookCreateRequest {
  readonly isbn: string;
  readonly title: string | null;
  readonly author: string | null;
  /** Texto legado: o backend o preenche com os nomes de `genre_ids` (Issue #174). */
  readonly genre?: string | null;
  /** Categorias do catálogo; sincronizam `book_genres` e valem para o catálogo público. */
  readonly genre_ids?: readonly number[];
  readonly cover_url: string | null;
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
  readonly genres?: readonly BookGenre[];
  readonly cover_url: string | null;
  readonly is_active: boolean;
  readonly initial_copy: CopyResponse | null;
}

export interface BookUpdateRequest {
  readonly title?: string | null;
  readonly author?: string | null;
  readonly genre?: string | null;
  /** Substitui as categorias do catálogo da obra; `[]` remove todas. */
  readonly genre_ids?: readonly number[];
  readonly isbn?: string | null;
  readonly publication_year?: number | null;
  readonly publisher?: string | null;
  readonly edition?: string | null;
  readonly cover_url?: string | null;
  readonly is_active?: boolean;
}

export interface BookDetail extends BookResponse {
  readonly publication_year?: number | null;
  readonly publisher?: string | null;
  readonly edition?: string | null;
  readonly copies: CopyResponse[];
}

export interface BookMetadata {
  readonly isbn: string;
  readonly title: string;
  readonly author: string;
  /** Informativo (Issue #176): a categoria externa nunca vira categoria do acervo. */
  readonly genre: string | null;
  readonly cover_url?: string | null;
  readonly publisher?: string | null;
  readonly publication_year?: number | null;
}
