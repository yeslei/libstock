import { DestroyRef } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { Subject, of, throwError } from 'rxjs';

import { snackbarMessage, snackbarVariant } from '../../shared/components/snackbar/snackbar.testing';
import { ActionFlow, PendingAction } from './desk-flow';

describe('ActionFlow: feedback por snackbar e estado de recuperação', () => {
  function setup() {
    const after = jasmine.createSpy('after');
    const flow = TestBed.runInInjectionContext(() => new ActionFlow(TestBed.inject(DestroyRef), after));
    return { flow, after };
  }

  const action = (run: PendingAction['run'], extra: Partial<PendingAction> = {}): PendingAction => ({
    title: 'Confirmar?', details: [], confirmLabel: 'Confirmar', run, success: () => 'Feito.', ...extra,
  });

  it('só anuncia sucesso depois da resposta 2xx', () => {
    const { flow, after } = setup();
    const response = new Subject<unknown>();
    flow.ask(action(() => response));
    flow.confirm();
    expect(snackbarMessage()).toBe('');
    expect(flow.submitting()).toBeTrue();
    response.next({});
    response.complete();
    expect(snackbarMessage()).toBe('Feito.');
    expect(snackbarVariant()).toBe('success');
    expect(flow.saveFailed()).toBeFalse();
    expect(after).toHaveBeenCalledOnceWith(true);
  });

  it('recusa de domínio vai ao snackbar: 409 como atenção e demais 4xx como erro', () => {
    for (const [status, variant] of [[409, 'warning'], [422, 'error'], [404, 'error']] as const) {
      const { flow, after } = setup();
      flow.ask(action(() => throwError(() => ({ status, detail: 'Recusado.' }))));
      flow.confirm();
      expect(snackbarMessage()).toBe('Recusado.');
      expect(snackbarVariant()).toBe(variant);
      expect(flow.saveFailed()).toBeFalse();
      expect(after).toHaveBeenCalledOnceWith(false);
    }
  });

  it('falha de rede (0) ou 5xx liga "Não foi possível salvar", não usa snackbar e não reenvia', () => {
    for (const status of [0, 500, 503]) {
      const { flow } = setup();
      const run = jasmine.createSpy('run').and.returnValue(throwError(() => ({ status, detail: 'Falha.' })));
      flow.ask(action(run));
      flow.confirm();
      expect(flow.saveFailed()).toBeTrue();
      expect(snackbarMessage()).toBe('');
      expect(run).toHaveBeenCalledTimes(1);
      expect(flow.confirming()).toBeNull();
      flow.ask(action(() => of({})));
      expect(flow.saveFailed()).toBeFalse();
    }
  });

  it('onError que trata a falha suprime snackbar e estado de recuperação', () => {
    const { flow } = setup();
    flow.ask(action(() => throwError(() => ({ status: 409, detail: 'Bloqueada.' })), { onError: () => true }));
    flow.confirm();
    expect(snackbarMessage()).toBe('');
    expect(flow.saveFailed()).toBeFalse();
  });

  it('bloqueia envio duplicado enquanto a resposta não chega', () => {
    const { flow } = setup();
    const run = jasmine.createSpy('run').and.returnValue(new Subject());
    flow.ask(action(run));
    flow.confirm();
    flow.confirm();
    expect(run).toHaveBeenCalledTimes(1);
  });
});
