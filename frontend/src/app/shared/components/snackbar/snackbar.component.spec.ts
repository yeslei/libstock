import { TestBed, fakeAsync, tick } from '@angular/core/testing';
import { SnackbarComponent } from './snackbar.component';
import { SnackbarService, SnackbarVariant } from './snackbar.service';

describe('Snackbar compartilhado', () => {
  function setup() {
    TestBed.configureTestingModule({ imports: [SnackbarComponent], providers: [SnackbarService] });
    const fixture = TestBed.createComponent(SnackbarComponent);
    const service = TestBed.inject(SnackbarService);
    fixture.detectChanges();
    return { fixture, service, root: fixture.nativeElement as HTMLElement };
  }

  for (const variant of ['success', 'error', 'warning', 'info'] as SnackbarVariant[]) {
    it(`anuncia ${variant} com texto, ícone decorativo e variante visual`, () => {
      const { fixture, service, root } = setup();
      service.show('Resultado recebido.', variant);
      fixture.detectChanges();
      const notification = root.querySelector('.snackbar')!;
      const region = notification.parentElement!;
      expect(root.querySelectorAll('.snackbar-live').length).toBe(2);
      expect(notification.classList).toContain(`snackbar--${variant}`);
      expect(region.getAttribute('role')).toBe(variant === 'error' ? 'alert' : 'status');
      expect(region.getAttribute('aria-live')).toBe(variant === 'error' ? 'assertive' : 'polite');
      expect(region.getAttribute('aria-atomic')).toBe('true');
      expect(notification.textContent).toContain('Resultado recebido.');
      expect(root.querySelector('.snackbar__icon')?.getAttribute('aria-hidden')).toBe('true');
      service.dismiss();
    });
  }

  it('mantém as regiões vivas no DOM, vazias, antes de qualquer mensagem', () => {
    const { root } = setup();
    const regions = Array.from(root.querySelectorAll('.snackbar-live'));
    expect(regions.map((region) => region.getAttribute('role'))).toEqual(['status', 'alert']);
    expect(regions.every((region) => region.children.length === 0)).toBeTrue();
  });

  it('fecha pelo botão e por Escape dentro da mensagem, sem roubar o foco ao abrir', () => {
    const { fixture, service, root } = setup();
    const before = document.activeElement;
    service.show('Erro.', 'error');
    fixture.detectChanges();
    expect(document.activeElement).toBe(before);
    (root.querySelector('[aria-label="Fechar mensagem"]') as HTMLButtonElement).click();
    fixture.detectChanges();
    expect(root.querySelector('.snackbar')).toBeNull();
    service.show('Aviso.', 'warning');
    fixture.detectChanges();
    root.querySelector('button')!.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    fixture.detectChanges();
    expect(root.querySelector('.snackbar')).toBeNull();
  });

  it('substitui a mensagem e cancela o temporizador anterior', fakeAsync(() => {
    const { fixture, service, root } = setup();
    service.show('Primeira.', 'success');
    tick(4000);
    service.show('Segunda.', 'info');
    tick(4000);
    fixture.detectChanges();
    expect(root.querySelectorAll('.snackbar').length).toBe(1);
    expect(root.textContent).toContain('Segunda.');
    expect(root.textContent).not.toContain('Primeira.');
    tick(4000);
    fixture.detectChanges();
    expect(root.querySelector('.snackbar')).toBeNull();
  }));

  it('mantém erros, avisos e ações até fechamento explícito', fakeAsync(() => {
    const { fixture, service, root } = setup();
    for (const variant of ['error', 'warning'] as SnackbarVariant[]) {
      service.show('Requer atenção.', variant);
      tick(60000);
      expect(service.notification()?.message).toBe('Requer atenção.');
    }
    const action = jasmine.createSpy('ação');
    service.show('Consulta disponível.', 'info', { label: 'Consultar', run: action });
    tick(60000);
    fixture.detectChanges();
    const button = Array.from(root.querySelectorAll('button')).find((item) => item.textContent?.trim() === 'Consultar')!;
    button.click();
    expect(action).toHaveBeenCalledTimes(1);
    expect(service.notification()).toBeNull();
  }));

  it('preserva nova mensagem publicada pela ação', () => {
    const { service } = setup();
    service.show('Consultar.', 'info', { label: 'Consultar', run: () => service.show('Consulta atualizada.', 'success') });
    service.act();
    expect(service.notification()?.message).toBe('Consulta atualizada.');
    service.dismiss();
  });

  it('limpa estado e temporizador ao destruir o escopo', fakeAsync(() => {
    const { service } = setup();
    service.show('Sucesso.', 'success');
    TestBed.resetTestingModule();
    expect(service.notification()).toBeNull();
    tick(8000);
    expect(service.notification()).toBeNull();
  }));
});
