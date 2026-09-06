export interface BookCreateRequest {
  readonly isbn: string;
  readonly title: string | null;
  readonly author: string | null;
  readonly genre: string | null;
}

/** Espelha `BookResponse`; os opcionais permanecem anuláveis no OpenAPI. */
export interface BookResponse extends BookCreateRequest {
  readonly id: number;
}
