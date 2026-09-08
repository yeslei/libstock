import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { HowItWorksComponent } from './how-it-works.component';

describe('HowItWorksComponent', () => {
  let fixture: ComponentFixture<HowItWorksComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [HowItWorksComponent],
      providers: [provideRouter([])],
    }).compileComponents();

    fixture = TestBed.createComponent(HowItWorksComponent);
    fixture.detectChanges();
  });

  it('explica o acervo híbrido e suas duas destinações', () => {
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';

    expect(text).toContain('Obra e exemplar são diferentes');
    expect(text).toContain('Didático');
    expect(text).toContain('Comercial');
    expect(text).toContain('Escopo atual');
  });
});
