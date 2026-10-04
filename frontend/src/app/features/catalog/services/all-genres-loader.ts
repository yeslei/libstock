import { DestroyRef, inject, signal } from '@angular/core';

import { Genre } from '../models/catalog.model';
import { CatalogService } from './catalog.service';

/**
 * Estado do chip "Mais": ao abrir, troca as categorias em destaque pela lista
 * completa (`GET /catalog/genres?all=true`), buscada uma única vez. Se a
 * consulta falhar, os destaques continuam e a tela avisa.
 * Deve ser criado em contexto de injeção (campo de componente).
 */
export function createAllGenresLoader() {
  const catalog = inject(CatalogService);
  const destroyRef = inject(DestroyRef);
  const expanded = signal(false);
  const loading = signal(false);
  const failed = signal(false);
  const all = signal<Genre[] | null>(null);

  function toggle(): void {
    const next = !expanded();
    expanded.set(next);
    if (!next || all() !== null || loading()) return;
    loading.set(true);
    failed.set(false);
    const subscription = catalog.getAllGenres().subscribe({
      next: (genres) => { all.set(genres); loading.set(false); },
      error: () => { loading.set(false); failed.set(true); expanded.set(false); },
    });
    destroyRef.onDestroy(() => subscription.unsubscribe());
  }

  return {
    expanded,
    loading,
    failed,
    toggle,
    /** Lista a exibir: completa quando aberta e carregada; senão os destaques. */
    visible: (featured: readonly Genre[]): readonly Genre[] =>
      expanded() && all() ? all()! : featured,
  };
}
