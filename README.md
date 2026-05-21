# FreeSystemDoctor PRO

> Premium tier of [FreeSystemDoctor](https://github.com/caytec/freesystemdoctor) — Cloud sync, per-game profiles, multi-PC, priority support. **Lifetime license available.**

[![Pricing](https://img.shields.io/badge/Pro-99%20PLN%2Fyr-blue.svg)](https://caytec.github.io/freesystemdoctor-pro#pricing)
[![Lifetime](https://img.shields.io/badge/Lifetime-199%20PLN-gold.svg)](https://caytec.github.io/freesystemdoctor-pro#pricing)
[![Ultimate](https://img.shields.io/badge/Ultimate-199%20PLN%2Fyr-purple.svg)](https://caytec.github.io/freesystemdoctor-pro#pricing)

🌐 **Strona:** [caytec.github.io/freesystemdoctor-pro](https://caytec.github.io/freesystemdoctor-pro)

## Co to jest

Wersja Pro/Ultimate aplikacji FreeSystemDoctor. Free wersja jest i zawsze będzie darmowa pod [caytec/freesystemdoctor](https://github.com/caytec/freesystemdoctor). Pro istnieje aby projekt mógł być rozwijany **bez reklam, telemetrii ani sprzedaży danych**.

## Funkcje Pro (vs Free)

| Funkcja | Free | Pro | Ultimate |
|---|:-:|:-:|:-:|
| Cloud sync configów | ❌ | ✓ 3 PC | ✓ 5 PC |
| Auto-scheduler z cron builder | ❌ | ✓ | ✓ |
| Per-game profile (50+ presetów) | ❌ | ✓ | ✓ |
| Discord / email alerts | ❌ | ✓ | ✓ |
| Driver updater premium | ❌ | ✓ | ✓ |
| Software updater (3k+ apps) | ❌ | ✓ | ✓ |
| Branded PDF/HTML raporty | ❌ | ✓ | ✓ |
| Priorytetowy support | ❌ | 24h | priority |
| Multi-PC management (web panel) | ❌ | ❌ | ✓ |
| Custom AI prompts | ❌ | ❌ | ✓ |
| 30-dniowa historia hardware | ❌ | ❌ | ✓ |
| Anti-cheat sandbox tester | ❌ | ❌ | ✓ |
| Bandwidth limiter per app | ❌ | ❌ | ✓ |
| Komercyjna licencja | ❌ | ❌ | ✓ |

## Cennik

| Tier | Roczna | Lifetime |
|---|---|---|
| **Pro** | 99 zł (~$25) | 199 zł (~$50) |
| **Ultimate** | 199 zł (~$50) | 399 zł (~$100) |

- 30 dni money-back guarantee
- Faktura VAT na życzenie
- Auto-renewal **WYŁĄCZONY** by default (nie jak CCleaner/Avast)
- BLIK / Przelewy24 / Stripe / Paddle

## Struktura repo

```
.
├── index.html              Landing page
├── checkout.html           Checkout (Stripe/Paddle/Przelewy24)
├── style.css               Premium dark + gold theme
├── license/
│   └── license_manager.py  License validation + online activation
├── pro_features/
│   ├── cloud_sync.py       Dropbox / GDrive / S3 sync
│   ├── per_game_profiles.py 50+ anti-cheat-safe game presets
│   └── alerts.py           Discord webhooks + email notifications
├── dist/
│   └── FreeSystemDoctorPro.exe   Pro build (license-gated)
└── .github/workflows/
    └── deploy-pages.yml    GitHub Pages auto-deploy
```

## Dla developera

```bash
# Sklonuj repo
git clone https://github.com/caytec/freesystemdoctor-pro
cd freesystemdoctor-pro

# Test licensingu (CLI)
python licensing/license_manager.py
python licensing/license_manager.py activate FSD-PRO-2026-AB12CD-7E3F

# Test Pro features (wymaga ważnej licencji)
python -c "from pro_features.cloud_sync import sync_now; print(sync_now())"
```

## Licencja

- Strona, system licensingu, Pro features: **kod publiczny pod MIT**
- Klucze licencyjne: generowane przez serwer aktywacyjny (kod serwera nie w repo)
- Same EXE: dystrybuowane jako commercial product

## Linki

- 🌐 [Sklep / Landing](https://caytec.github.io/freesystemdoctor-pro)
- 💼 [Free wersja](https://github.com/caytec/freesystemdoctor)
- 📧 [Support](mailto:support@freesystemdoctor.pl)
