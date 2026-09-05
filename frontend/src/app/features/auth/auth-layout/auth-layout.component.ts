import { ChangeDetectionStrategy, Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';

/**
 * Moldura das telas de autenticação: fundo creme da marca, card centralizado e
 * logo no topo — âncora de contexto para quem chega por um link direto
 * (Nielsen #6, reconhecimento em vez de memorização).
 */
@Component({
  selector: 'app-auth-layout',
  standalone: true,
  imports: [RouterOutlet],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './auth-layout.component.html',
  styleUrl: './auth-layout.component.scss',
})
export class AuthLayoutComponent {}
