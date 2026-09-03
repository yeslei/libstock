# Identidade Visual — LibStock

Fonte de verdade das cores da marca. As cores primárias foram extraídas por
amostragem dos pixels de `frontend/assets/logo-libstock-full.png`.

Conceito: **verde escuro** (biblioteca, confiança) com acentos em **dourado** e
**terracota**.

## Paleta da marca

| Token | Hex | Amostra | Origem na logo |
|---|---|---|---|
| `$verde-profundo` | `#0A3B29` | ▉ | dominante — "Lib", contorno do livro |
| `$verde-sage` | `#496B4C` | ▉ | "Stock", livro grande |
| `$verde-medio` | `#2F573C` | ▉ | tom intermediário |
| `$dourado` | `#A99654` | ▉ | marcador de página, livro mostarda |
| `$terracota` | `#B36626` | ▉ | livro laranja queimado |
| `$verde-acinzentado` | `#768E83` | ▉ | neutro frio |
| `$verde-claro` | `#AFBDB6` | ▉ | bordas, divisores |
| `$creme` | `#FEF8F0` | ▉ | fundo off-white da marca |

## Tokens semânticos

| Token | Valor | Uso |
|---|---|---|
| `$primary` | `$verde-profundo` | botões principais, links, foco |
| `$primary-hover` | `#0D4E36` | hover do primário (~8% mais claro) |
| `$secondary` | `$verde-sage` | botões secundários, badges |
| `$accent` | `$dourado` | destaques e ícones decorativos |
| `$warning` | `$terracota` | avisos |
| `$error` | `#B3261E` | erros — vermelho harmonizado com a terracota |
| `$success` | `$verde-sage` | confirmações |

## Superfícies e texto

| Token | Valor | Uso |
|---|---|---|
| `$bg-page` | `$creme` | fundo das páginas de autenticação |
| `$bg-surface` | `#FFFFFF` | card do formulário |
| `$text-primary` | `#1A1A1A` | texto principal |
| `$text-secondary` | `#6B5644` | marrom da tagline, texto de apoio |
| `$border` | `$verde-claro` | bordas de input em repouso |
| `$border-focus` | `$primary` | bordas de input em foco |

## Elevação

```scss
$shadow-sm: 0 1px 3px rgba(10, 59, 41, 0.10);
$shadow-md: 0 10px 24px rgba(10, 59, 41, 0.12);
```

## Contraste (WCAG 2.1 AA)

- `$verde-profundo` sobre branco ≈ **11:1** (AAA).
- Branco sobre `$verde-profundo` ≈ **11:1** (AAA).
- `$dourado` sobre branco ≈ **2,6:1** — **nunca use para texto**. Apenas
  elementos decorativos, bordas e ícones não informativos.
- Texto exige no mínimo **4,5:1**; texto grande (≥ 18,66px bold / 24px), 3:1.

## Assets

Em `frontend/assets/`:

| Arquivo | Uso |
|---|---|
| `logo-libstock-full.png` | ícone + wordmark + tagline (vertical) |
| `logo-libstock-wordmark-tagline.png` | wordmark + tagline |
| `logo-libstock-wordmark.png` | somente "LibStock" |
| `logo-libstock-icon.png` | somente o ícone |
| `favicon.ico` | favicon |
| `apple-touch-icon.png` | iOS |
| `android-chrome-192x192.png` / `-512x512.png` | PWA / Android |

Texto alternativo padrão da logo completa:
`LibStock — Livros, Gestão, Confiança`.

Nas telas de autenticação: `logo-libstock-full.png` no topo do card
(`max-width: 180px`); abaixo de 480px, trocar por `logo-libstock-wordmark.png`
para economizar altura vertical.

## Implementação

Os tokens acima vivem em [`frontend/src/styles/variables.scss`](frontend/src/styles/variables.scss).
