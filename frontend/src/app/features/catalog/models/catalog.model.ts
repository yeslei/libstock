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

export interface ModalityAvailability {
  readonly can_reserve?: boolean;
  readonly available: boolean | null;
  readonly available_count: number | null;
  readonly configured: boolean;
  readonly price: string | null;
}

export interface CatalogBookDetail extends CatalogBook {
  readonly isbn: string | null;
  readonly availability: {
    readonly loan: ModalityAvailability;
    readonly sale: ModalityAvailability;
    readonly local_consultation: ModalityAvailability;
  };
}

export interface BookAvailability {
  readonly id: number;
  readonly title: string;
  readonly is_available: boolean;
  readonly available_copies_count: number;
}

export interface PagedBooks {
  /** Vem do backend para a tela ter o nome exibível, não só o slug da URL. */
  readonly genre: Genre;
  readonly items: CatalogBook[];
  readonly total: number;
  readonly page: number;
  readonly page_size: number;
}

export type { LoadState } from '../../../core/models/load-state.model';
