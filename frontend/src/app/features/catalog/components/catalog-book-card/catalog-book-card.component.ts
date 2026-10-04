import { RouterLink } from '@angular/router';
import { ChangeDetectionStrategy, Component, input, signal } from '@angular/core';
import { CatalogBook } from '../../models/catalog.model';

@Component({
  selector: 'app-catalog-book-card',
  standalone: true,
  imports: [RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './catalog-book-card.component.html',
  styleUrl: './catalog-book-card.component.scss',
})
export class CatalogBookCardComponent {
  readonly book = input.required<CatalogBook>();
  protected readonly failedCover = signal<string | null>(null);
}
