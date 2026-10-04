import { TestBed, fakeAsync, tick } from '@angular/core/testing';
import { Subject, of, throwError } from 'rxjs';
import { UserService } from '../../../core/services/user.service';
import { ResetPasswordResponse } from '../../../core/models/user.model';
import { SnackbarService } from '../../../shared/components/snackbar/snackbar.service';
import { adminUser } from '../user-fixtures';
import { UserPasswordResetComponent } from './user-password-reset.component';

describe('Redefinição assistida de senha', () => {
  function setup() {
    const api = jasmine.createSpyObj<UserService>('UserService', ['resetPassword']);
    api.resetPassword.and.returnValue(of({ user_id: 2, message: 'Senha redefinida com sucesso.' }));
    TestBed.configureTestingModule({ imports: [UserPasswordResetComponent], providers: [{ provide: UserService, useValue: api }] });
    const fixture = TestBed.createComponent(UserPasswordResetComponent);
    fixture.componentRef.setInput('user', adminUser());
    fixture.detectChanges();
    const root = fixture.nativeElement as HTMLElement;
    const feedback = TestBed.inject(SnackbarService);
    function click(label: string) {
      const button = Array.from(root.querySelectorAll('button')).find((item) => item.textContent?.trim() === label)!;
      expect(button).withContext(label).toBeTruthy();
      button.click(); fixture.detectChanges(); tick(); fixture.detectChanges();
    }
    function fill(password = 'nova-senha-teste', confirmation = password) {
      for (const [id, value] of [['reset-password', password], ['reset-confirmation', confirmation]]) {
        const input = root.querySelector<HTMLInputElement>(`#${id}`)!;
        input.value = value; input.dispatchEvent(new Event('input', { bubbles: true }));
      }
      fixture.detectChanges();
    }
    return { api, fixture, root, feedback, click, fill };
  }

  it('valida obrigatoriedade, comprimento e confirmação antes de qualquer envio', fakeAsync(() => {
    const ctx = setup();
    ctx.click('Redefinir senha'); ctx.click('Continuar');
    expect(ctx.root.textContent).toContain('Informe a nova senha.');
    ctx.fill('curta'); ctx.click('Continuar');
    expect(ctx.root.textContent).toContain('pelo menos 8');
    ctx.fill('x'.repeat(129)); ctx.click('Continuar');
    expect(ctx.root.textContent).toContain('no máximo 128');
    ctx.fill('nova-senha-teste', 'outra-senha'); ctx.click('Continuar');
    expect(ctx.root.textContent).toContain('As senhas não coincidem.');
    expect(ctx.api.resetPassword).not.toHaveBeenCalled();
    ctx.click('Cancelar');
  }));

  it('confirma nome/e-mail sem senha e só mostra sucesso após resposta, sem envio duplo', fakeAsync(() => {
    const ctx = setup();
    const pending = new Subject<ResetPasswordResponse>();
    ctx.api.resetPassword.and.returnValue(pending);
    ctx.click('Redefinir senha'); ctx.fill(); ctx.click('Continuar');
    const dialog = ctx.root.querySelector('[role="alertdialog"]')!;
    expect(dialog.textContent).toContain('Maria Silva');
    expect(dialog.textContent).toContain('maria@email.com');
    expect(dialog.textContent).not.toContain('nova-senha-teste');
    expect(dialog.querySelector('input')).toBeNull();
    expect(document.activeElement).toBe(dialog);
    expect(ctx.api.resetPassword).not.toHaveBeenCalled();
    ctx.click('Confirmar redefinição');
    expect(ctx.api.resetPassword).toHaveBeenCalledOnceWith(2, { new_password: 'nova-senha-teste' });
    expect(ctx.feedback.notification()).toBeNull();
    const confirm = ctx.root.querySelector('[aria-busy="true"]') as HTMLButtonElement;
    expect(confirm.disabled).toBeTrue(); confirm.click();
    expect(ctx.api.resetPassword).toHaveBeenCalledTimes(1);
    pending.next({ user_id: 2, message: 'Senha redefinida com sucesso.' });
    ctx.fixture.detectChanges(); tick(); ctx.fixture.detectChanges();
    expect(ctx.root.querySelector('.snackbar')?.textContent).toContain('Senha redefinida com sucesso.');
    ctx.click('Redefinir senha');
    expect(ctx.root.querySelector<HTMLInputElement>('#reset-password')?.value).toBe('');
    expect(ctx.root.querySelector<HTMLInputElement>('#reset-confirmation')?.value).toBe('');
    ctx.feedback.dismiss(); ctx.click('Cancelar');
  }));

  it('cancela confirmação limpando as senhas e sem POST', fakeAsync(() => {
    const ctx = setup();
    ctx.click('Redefinir senha'); ctx.fill(); ctx.click('Continuar'); ctx.click('Cancelar');
    expect(ctx.api.resetPassword).not.toHaveBeenCalled();
    ctx.click('Redefinir senha');
    expect(ctx.root.querySelector<HTMLInputElement>('#reset-password')?.value).toBe('');
    ctx.click('Cancelar');
  }));

  for (const status of [0, 500]) {
    it(`trata resultado incerto (${status}) sem repetir ou fingir consulta de credencial`, fakeAsync(() => {
      const ctx = setup();
      ctx.api.resetPassword.and.returnValue(throwError(() => ({ status, detail: 'Falha.' })));
      ctx.click('Redefinir senha'); ctx.fill(); ctx.click('Continuar'); ctx.click('Confirmar redefinição');
      expect(ctx.root.textContent).toContain('Não foi possível confirmar o resultado');
      expect(ctx.root.textContent).toContain('Confira com o usuário');
      expect(ctx.feedback.notification()).toBeNull();
      tick(10000);
      expect(ctx.api.resetPassword).toHaveBeenCalledTimes(1);
      ctx.click('Iniciar nova redefinição');
      expect(ctx.root.querySelector<HTMLInputElement>('#reset-password')?.value).toBe('');
      expect(ctx.api.resetPassword).toHaveBeenCalledTimes(1);
      ctx.click('Cancelar');
    }));
  }

  it('exibe erro conhecido sem sucesso e sem conservar a senha', fakeAsync(() => {
    const ctx = setup();
    ctx.api.resetPassword.and.returnValue(throwError(() => ({ status: 403, detail: 'Permissão insuficiente.' })));
    ctx.click('Redefinir senha'); ctx.fill(); ctx.click('Continuar'); ctx.click('Confirmar redefinição');
    expect(ctx.root.textContent).toContain('Permissão insuficiente.');
    expect(ctx.feedback.notification()).toBeNull();
    expect(ctx.root.querySelector<HTMLInputElement>('#reset-password')?.value).toBe('');
    ctx.click('Cancelar');
  }));

  it('ignora resposta tardia depois de destruir a tela', fakeAsync(() => {
    const ctx = setup();
    const pending = new Subject<ResetPasswordResponse>();
    ctx.api.resetPassword.and.returnValue(pending);
    ctx.click('Redefinir senha'); ctx.fill(); ctx.click('Continuar'); ctx.click('Confirmar redefinição');
    ctx.fixture.destroy();
    pending.next({ user_id: 2, message: 'Senha redefinida com sucesso.' }); tick();
    expect(ctx.feedback.notification()).toBeNull();
  }));

  it('descarta credencial e resposta antiga ao trocar o usuário alvo', fakeAsync(() => {
    const ctx = setup();
    const pending = new Subject<ResetPasswordResponse>();
    ctx.api.resetPassword.and.returnValue(pending);
    ctx.click('Redefinir senha'); ctx.fill(); ctx.click('Continuar'); ctx.click('Confirmar redefinição');
    ctx.fixture.componentRef.setInput('user', adminUser({ id: 9 })); ctx.fixture.detectChanges();
    pending.next({ user_id: 2, message: 'Senha redefinida com sucesso.' });
    ctx.fixture.detectChanges();
    expect(ctx.feedback.notification()).toBeNull();
    ctx.click('Redefinir senha');
    expect(ctx.root.querySelector<HTMLInputElement>('#reset-password')?.value).toBe('');
    ctx.click('Cancelar');
  }));
});
