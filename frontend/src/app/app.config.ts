import { provideHttpClient, withInterceptors } from '@angular/common/http';
import {
  ApplicationConfig,
  inject,
  provideAppInitializer,
  provideBrowserGlobalErrorListeners,
  provideZoneChangeDetection,
} from '@angular/core';
import { provideRouter, withComponentInputBinding, withInMemoryScrolling } from '@angular/router';

import { routes } from './app.routes';
import { authInterceptor } from './core/interceptors/auth.interceptor';
import { errorInterceptor } from './core/interceptors/error.interceptor';
import { AuthService } from './core/services/auth.service';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideZoneChangeDetection({ eventCoalescing: true }),
    provideRouter(
      routes,
      withComponentInputBinding(),
      withInMemoryScrolling({ scrollPositionRestoration: 'enabled' }),
    ),
    // A ordem importa: o errorInterceptor é o mais externo, então normaliza o
    // erro que sobrar *depois* de o authInterceptor ter tentado o refresh.
    provideHttpClient(withInterceptors([errorInterceptor, authInterceptor])),
    // O access token vive só em memória; a sessão é recuperada no boot pelo
    // cookie HttpOnly de refresh. Sem isto, todo reload cairia no login.
    provideAppInitializer(() => inject(AuthService).restoreSession()),
  ],
};
