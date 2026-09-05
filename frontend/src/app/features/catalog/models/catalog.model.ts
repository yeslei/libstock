/** Destino de um exemplar. Espelha `DestinationType` do backend. */
export type OfferDestination = 'COMMERCIAL' | 'DIDACTIC';

export interface BookOffer {
  readonly destination: OfferDestination;
  /**
   * Falso é o "Esgotado" da US02: o título continua no catálogo, sem
   * exemplar livre no momento.
   */
  readonly available: boolean;
  /** Só vem preenchido em oferta de venda — empréstimo não tem preço. */
  readonly price: string | null;
  /** RF07: exemplar de venda emprestado admite Reserva de Compra. */
  readonly can_reserve: boolean;
}

export interface Genre {
  readonly id: number;
  readonly name: string;
  readonly slug: string;
}

export interface CatalogBook {
  readonly id: number;
  readonly title: string;
  readonly author: string;
  readonly cover_url: string | null;
  /** Um livro pode estar em vários gêneros ao mesmo tempo. */
  readonly genres: string[];
  /** Um mesmo livro pode estar à venda e disponível para empréstimo. */
  readonly offers: BookOffer[];
}

export interface PagedBooks {
  /** Vem do backend para a tela ter o nome exibível, não só o slug da URL. */
  readonly genre: Genre;
  readonly items: CatalogBook[];
  readonly total: number;
  readonly page: number;
  readonly page_size: number;
}

/**
 * Estado de carregamento como união discriminada, seguindo o padrão de
 * `FormState` em `core/models/auth.model.ts`: flags soltas permitiriam
 * combinações inválidas como "carregando e com erro" ao mesmo tempo.
 */
export type LoadState<T> =
  | { status: 'loading' }
  | { status: 'loaded'; data: T }
  | { status: 'error'; message: string };
