import { Component, signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { Observable, of, throwError } from 'rxjs';

import { Genre } from '../../../catalog/models/catalog.model';
import { CatalogService } from '../../../catalog/services/catalog.service';
import { GenrePickerComponent } from './genre-picker.component';

const GENRES: Genre[] = [
  { id: 1, name: 'Ficção', slug: 'ficcao' },
  { id: 4, name: 'Fantasia', slug: 'fantasia' },
  { id: 7, name: 'Romance', slug: 'romance' },
];

@Component({
  standalone: true,
  imports: [GenrePickerComponent],
  template: `<app-genre-picker [selected]="value()" [disabled]="off()" idPrefix="t" (selectedChange)="set($event)" />`,
})
class HostComponent {
  readonly value = signal<number[]>([4]);
  readonly off = signal(false);
  readonly set = (genres: Genre[]) => this.value.set(genres.map((genre) => genre.id));
}

function setup(genres$: Observable<Genre[]>) {
  const catalog = jasmine.createSpyObj<CatalogService>('CatalogService', ['getAllGenres']);
  catalog.getAllGenres.and.returnValue(genres$);
  TestBed.configureTestingModule({ imports: [HostComponent], providers: [{ provide: CatalogService, useValue: catalog }] });
  const fixture = TestBed.createComponent(HostComponent);
  fixture.detectChanges();
  const root = fixture.nativeElement as HTMLElement;
  const boxes = () => Array.from(root.querySelectorAll<HTMLInputElement>('input[type="checkbox"]'));
  return { fixture, root, catalog, boxes, host: fixture.componentInstance };
}

describe('GenrePickerComponent', () => {
  it('lista todas as categorias do catálogo e marca as selecionadas', () => {
    const { catalog, boxes } = setup(of(GENRES));
    expect(catalog.getAllGenres).toHaveBeenCalledTimes(1);
    expect(boxes().map((box) => box.id)).toEqual(['t-1', 't-4', 't-7']);
    expect(boxes().map((box) => box.checked)).toEqual([false, true, false]);
  });

  it('emite a lista de ids ao marcar e desmarcar (seleção múltipla)', () => {
    const { fixture, boxes, host } = setup(of(GENRES));
    boxes()[2].click();
    fixture.detectChanges();
    expect(host.value()).toEqual([4, 7]);
    boxes()[1].click();
    fixture.detectChanges();
    expect(host.value()).toEqual([7]);
    expect(boxes().map((box) => box.checked)).toEqual([false, false, true]);
  });

  it('bloqueia a escolha quando desabilitado', () => {
    const { fixture, root, host } = setup(of(GENRES));
    host.off.set(true);
    fixture.detectChanges();
    expect(root.querySelector('fieldset')?.disabled).toBeTrue();
  });

  it('avisa a falha ao carregar e permite tentar novamente', () => {
    const { fixture, root, catalog, boxes } = setup(throwError(() => new Error('falhou')));
    expect(root.textContent).toContain('Não foi possível carregar as categorias do catálogo.');
    catalog.getAllGenres.and.returnValue(of(GENRES));
    root.querySelector<HTMLButtonElement>('.genre-picker__retry')!.click();
    fixture.detectChanges();
    expect(boxes().length).toBe(3);
  });
});
