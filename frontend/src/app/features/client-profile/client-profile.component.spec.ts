import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { Subject, of, throwError } from 'rxjs';
import { ClientProfileComponent } from './client-profile.component';
import { NotificationPreference, NotificationPreferenceService } from './notification-preference.service';

describe('Preferência de notificações: perfil', () => {
  const current: NotificationPreference = { channel: 'IN_APP', email: 'client@example.com' };
  async function setup(failLoad = false) {
    const api = jasmine.createSpyObj<NotificationPreferenceService>('NotificationPreferenceService', ['get', 'update']);
    api.get.and.returnValue(failLoad ? throwError(() => ({ status: 500 })) : of(current));
    api.update.and.returnValue(of({ ...current, channel: 'EMAIL' }));
    TestBed.configureTestingModule({ imports: [ClientProfileComponent], providers: [provideRouter([]), { provide: NotificationPreferenceService, useValue: api }] });
    const fixture = TestBed.createComponent(ClientProfileComponent);
    fixture.detectChanges(); await fixture.whenStable(); fixture.detectChanges();
    const root = fixture.nativeElement as HTMLElement;
    async function select(value: string) {
      const field = root.querySelector('select')!;
      field.value = value; field.dispatchEvent(new Event('change'));
      fixture.detectChanges(); await fixture.whenStable(); fixture.detectChanges();
    }
    function click(label: string) {
      const button = Array.from(root.querySelectorAll<HTMLButtonElement>('button')).find((b) => b.textContent?.trim() === label)!;
      expect(button).withContext(label).toBeTruthy(); button.click(); fixture.detectChanges();
    }
    return { api, fixture, root, select, click };
  }

  it('carrega canal persistido e e-mail somente leitura, sem salvar sem alteração', async () => {
    const ctx = await setup();
    expect(ctx.root.textContent).toContain('client@example.com');
    expect(ctx.root.querySelector('input')).toBeNull();
    expect(ctx.root.querySelector('select')?.value).toBe('IN_APP');
    expect(ctx.root.querySelector<HTMLButtonElement>('[type=submit]')?.disabled).toBeTrue();
    expect(ctx.api.update).not.toHaveBeenCalled();
  });

  it('mostra sucesso apenas após resposta e impede envio duplicado', async () => {
    const ctx = await setup();
    const response = new Subject<NotificationPreference>();
    ctx.api.update.and.returnValue(response);
    await ctx.select('EMAIL'); ctx.click('Salvar preferência');
    expect(ctx.api.update).toHaveBeenCalledOnceWith('EMAIL');
    expect(ctx.root.textContent).not.toContain('Preferência de notificação salva.');
    expect(ctx.root.querySelector<HTMLButtonElement>('[type=submit]')?.disabled).toBeTrue();
    ctx.root.querySelector<HTMLFormElement>('form')!.dispatchEvent(new Event('submit'));
    expect(ctx.api.update).toHaveBeenCalledTimes(1);
    response.next({ ...current, channel: 'EMAIL' }); response.complete(); ctx.fixture.detectChanges();
    expect(ctx.root.textContent).toContain('Preferência de notificação salva.');
  });

  it('permite recuperar falha de leitura por consulta explícita', async () => {
    const ctx = await setup(true);
    expect(ctx.root.querySelector('form')).toBeNull();
    ctx.api.get.and.returnValue(of(current)); ctx.click('Atualizar consulta');
    await ctx.fixture.whenStable(); ctx.fixture.detectChanges();
    expect(ctx.root.querySelector('form')).not.toBeNull();
    expect(ctx.api.get).toHaveBeenCalledTimes(2);
  });

  for (const status of [0, 500]) {
    it(`consulta novamente após resultado incerto (${status}) sem repetir PATCH`, async () => {
      const ctx = await setup();
      ctx.api.update.and.returnValue(throwError(() => ({ status })));
      await ctx.select('EMAIL'); ctx.click('Salvar preferência');
      await ctx.fixture.whenStable(); ctx.fixture.detectChanges();
      expect(ctx.root.textContent).toContain('Não foi possível confirmar o resultado');
      expect(ctx.root.querySelector<HTMLSelectElement>('select')?.disabled).toBeTrue();
      ctx.api.get.and.returnValue(throwError(() => ({ status: 500 }))); ctx.click('Atualizar consulta');
      await ctx.fixture.whenStable(); ctx.fixture.detectChanges();
      expect(ctx.root.querySelector<HTMLSelectElement>('select')?.disabled).toBeTrue();
      expect(ctx.api.update).toHaveBeenCalledTimes(1);
      ctx.api.get.and.returnValue(of({ ...current, channel: 'EMAIL' })); ctx.click('Atualizar consulta');
      await ctx.fixture.whenStable(); ctx.fixture.detectChanges();
      expect(ctx.root.querySelector('select')?.value).toBe('EMAIL');
      expect(ctx.api.update).toHaveBeenCalledTimes(1);
      expect(ctx.root.textContent).not.toContain('Preferência de notificação salva.');
    });
  }

  it('apresenta recusa de domínio sem anunciar sucesso', async () => {
    const ctx = await setup();
    ctx.api.update.and.returnValue(throwError(() => ({ status: 403, detail: 'Cadastro de cliente inativo.' })));
    await ctx.select('EMAIL'); ctx.click('Salvar preferência');
    expect(ctx.root.textContent).toContain('Cadastro de cliente inativo.');
    expect(ctx.root.textContent).not.toContain('Preferência de notificação salva.');
  });
});
