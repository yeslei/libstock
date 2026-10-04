import { TestBed } from '@angular/core/testing';
import { ActivatedRoute, convertToParamMap, provideRouter } from '@angular/router';
import { AuthService } from '../../../core/services/auth.service';
import { LoginComponent } from './login.component';

describe('Orientação de recuperação assistida no login', () => {
  it('oferece orientação acessível ao balcão sem chamada de API ou envio de e-mail', () => {
    const auth = jasmine.createSpyObj<AuthService>('AuthService', ['login']);
    TestBed.configureTestingModule({ imports: [LoginComponent], providers: [
      provideRouter([]), { provide: AuthService, useValue: auth },
      { provide: ActivatedRoute, useValue: { snapshot: { queryParamMap: convertToParamMap({}) } } },
    ] });
    const fixture = TestBed.createComponent(LoginComponent);
    fixture.detectChanges();
    const root = fixture.nativeElement as HTMLElement;
    const button = root.querySelector<HTMLButtonElement>('[aria-controls="password-recovery-help"]')!;
    expect(button.disabled).toBeFalse();
    expect(button.getAttribute('aria-expanded')).toBe('false');
    button.click(); fixture.detectChanges();
    expect(button.getAttribute('aria-expanded')).toBe('true');
    expect(root.querySelector('#password-recovery-help')?.getAttribute('aria-live')).toBe('polite');
    expect(root.querySelector('#password-recovery-help')?.textContent).toContain('Procure o balcão da biblioteca para redefinir sua senha.');
    expect(root.querySelector('#password-recovery-help')?.textContent).toContain('Não enviamos recuperação por e-mail');
    expect(auth.login).not.toHaveBeenCalled();
    expect(root.textContent).not.toContain('em breve');
    button.click(); fixture.detectChanges();
    expect(root.querySelector('#password-recovery-help')?.textContent?.trim()).toBe('');
  });
});
