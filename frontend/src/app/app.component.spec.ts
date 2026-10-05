import { Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { Router, RouterOutlet, provideRouter } from '@angular/router';
import { AppComponent } from './app.component';
import { TokenStoreService } from './core/services/token-store.service';
import { RoleCode } from './core/models/user.model';

@Component({ selector: 'app-navbar', standalone: true, template: 'Header público' })
class NavbarStub {}
@Component({ standalone: true, template: 'Conteúdo' })
class PageStub {}

describe('Header por perfil', () => {
  for (const role of ['SELLER', 'STOCK_KEEPER', 'ADMINISTRATOR', 'USER'] as RoleCode[]) {
    it(`${role}: mantém a navegação correta na entrada e na gestão`, async () => {
      TestBed.configureTestingModule({ providers: [provideRouter([{ path: '**', component: PageStub }])] });
      TestBed.overrideComponent(AppComponent, { set: { imports: [RouterOutlet, NavbarStub] } });
      TestBed.inject(TokenStoreService).setSession('t', { id: 1, name: 'F', email: 'f@x.dev', role_codes: [role], created_at: '' });
      const fixture = TestBed.createComponent(AppComponent);
      for (const url of ['/', '/gestao/usuarios', '/balcao/acervo']) {
        await TestBed.inject(Router).navigateByUrl(url); fixture.detectChanges();
        expect(!!fixture.nativeElement.querySelector('app-navbar')).withContext(url).toBe(role === 'USER' && !url.startsWith('/balcao') && !url.startsWith('/gestao'));
      }
    });
  }
});
