# Deployment Guide — FreeSystemDoctor Pro Backend

End-to-end instrukcja postawienia produkcyjnej infrastruktury w **45 minut**.

## Komponenty

| Komponent | Provider | Cena/mc | Czas setupu |
|---|---|---|---|
| **Domena** `freesystemdoctor.pl` | OVH / nazwa.pl | 60 zł/rok | 10 min |
| **Activation API** `api.freesystemdoctor.pl` | Fly.io | 0–5 USD | 10 min |
| **Email delivery** (Resend) | Resend.com | 0 USD (do 3k/mc) | 10 min |
| **Payment processor** | Stripe | 1.4% + 1 PLN/tx | 10 min |
| **DNS / CDN** | Cloudflare | 0 USD | 5 min |

**Total fixed cost:** ~5 USD/mc + koszty domeny (60 zł/rok).

---

## 1. Domena (10 min)

### Polska opcja: nazwa.pl

1. https://www.nazwa.pl → szukaj `freesystemdoctor.pl`
2. Cena: ~60 zł/rok (.pl) lub ~80 zł/rok (.com.pl)
3. Po zakupie → panel klienta → DNS → zamień nameservery na Cloudflare (krok 4)

### Międzynarodowa opcja: Cloudflare Registrar

1. https://dash.cloudflare.com → Registrar (najtańsze, by-cost)
2. `freesystemdoctor.com` ~9 USD/rok
3. Domena automatycznie pod Cloudflare DNS

---

## 2. Cloudflare DNS (5 min)

1. https://dash.cloudflare.com → Add site → `freesystemdoctor.pl` (Free plan)
2. Dodaj rekordy DNS:

```
Type    Name                Content                          Proxy
A       @                   185.199.108.153                  ✓ (proxied)
A       @                   185.199.109.153                  ✓
A       @                   185.199.110.153                  ✓
A       @                   185.199.111.153                  ✓
CNAME   www                 caytec.github.io                 ✓
CNAME   pro                 caytec.github.io                 ✓
CNAME   api                 fsd-activation.fly.dev           ✗ (DNS only)
TXT     @                   "v=spf1 include:_spf.resend.com ~all"
TXT     resend._domainkey   "<from Resend dashboard>"
```

3. SSL/TLS → Full (strict)
4. Page Rules → Always Use HTTPS

### CNAME files w repo

Stwórz pliki `CNAME` w obu repo (już dodane przez ten commit):

- `caytec/freesystemdoctor/CNAME`        → `freesystemdoctor.pl`
- `caytec/freesystemdoctor-pro/CNAME`    → `pro.freesystemdoctor.pl`

Po pushu Pages automatycznie wystawi cert SSL Let's Encrypt na obu subdomenach.

---

## 3. Resend email (10 min)

1. https://resend.com → sign up (free tier: 3000 emails/mc)
2. Domains → Add `freesystemdoctor.pl`
3. Skopiuj rekordy DKIM/SPF → dodaj w Cloudflare DNS (krok 2)
4. Czekaj ~10 min na weryfikację
5. API Keys → Create → skopiuj `re_...` (to będzie `RESEND_API_KEY`)
6. Test: `curl -X POST https://api.resend.com/emails -H "Authorization: Bearer re_..." ...`

---

## 4. Fly.io activation server (10 min)

```bash
# Zainstaluj flyctl
curl -L https://fly.io/install.sh | sh

# Zaloguj
flyctl auth login

cd activation_server/

# Utwórz aplikację (przy pierwszym deployu)
flyctl launch --no-deploy --name fsd-activation --region waw

# Stwórz wolumen na SQLite (1 GB starcza na ~100k licencji)
flyctl volumes create fsd_data --region waw --size 1

# Ustaw sekrety
flyctl secrets set \
  LICENSE_HMAC_SECRET="$(openssl rand -hex 32)" \
  STRIPE_WEBHOOK_SECRET="whsec_..." \
  RESEND_API_KEY="re_..." \
  ADMIN_TOKEN="$(openssl rand -hex 24)"

# Deploy
flyctl deploy

# Sprawdź zdrowie
curl https://fsd-activation.fly.dev/healthz
```

W Cloudflare DNS dodaj `CNAME api → fsd-activation.fly.dev` (DNS only).
Po 5 min: `curl https://api.freesystemdoctor.pl/healthz` powinno działać.

### Alternatywnie: Railway (jeden klik)

1. https://railway.app → Login with GitHub
2. New Project → Deploy from GitHub repo → `caytec/freesystemdoctor-pro`
3. Root directory: `activation_server`
4. Add variables (jak wyżej)
5. Settings → Domains → Generate (lub custom `api.freesystemdoctor.pl`)

---

## 5. Stripe Payment Links (10 min)

1. https://dashboard.stripe.com → Products → Add product
2. Stwórz 4 produkty:

| Produkt | Cena | Recurring |
|---|---|---|
| FSD Pro Yearly | 99 PLN | Yes, 1 year |
| FSD Pro Lifetime | 199 PLN | No |
| FSD Ultimate Yearly | 199 PLN | Yes, 1 year |
| FSD Ultimate Lifetime | 399 PLN | No |

3. Każdy → Payment links → Create
4. W ustawieniach każdego linku dodaj **metadata**:
   - `tier`: `pro` lub `ultimate`
   - `period`: `yearly` lub `lifetime`
5. Skopiuj URL-e → wklej w `checkout.html` zamiast `PLACEHOLDER`

### Webhook

1. Stripe → Developers → Webhooks → Add endpoint
2. URL: `https://api.freesystemdoctor.pl/webhooks/stripe`
3. Event: `checkout.session.completed`
4. Skopiuj `Signing secret` (`whsec_...`) → wstaw jako `STRIPE_WEBHOOK_SECRET` w Fly

---

## 6. Test end-to-end (10 min)

```bash
# 1. Symuluj zakup (test mode w Stripe)
# Karta: 4242 4242 4242 4242 / 12/25 / 123 / dowolny ZIP

# 2. Sprawdź czy webhook trafił
flyctl logs   # albo Railway logs

# 3. Sprawdź czy klucz powstał w bazie
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
     https://api.freesystemdoctor.pl/admin/stats

# 4. Sprawdź czy mail przyszedł (sprawdź Resend dashboard → Logs)

# 5. Aktywuj klucz w aplikacji
python licensing/license_manager.py activate FSD-PRO-2026-XXXXXX-XXXX
```

---

## Monitoring kosztów

| Service | Free limit | Pierwszy zarzut |
|---|---|---|
| Cloudflare | unlimited DNS | 0 USD |
| Fly.io | 3 shared-CPU VMs, 3 GB persistent | $1.94/GB/mo over 3 GB |
| Resend | 3000 emails/mc, 100/dzień | $20/mc dla 50k emails |
| Stripe | tylko fee per tx | 1.4% + 1 PLN |

**Break-even:** 1 sprzedaż Pro/mc pokrywa koszty.

---

## Backups

```bash
# Codzienny backup SQLite (cron na Fly)
flyctl ssh console
sqlite3 /data/fsd.db ".backup /data/fsd-$(date +%F).db"

# Albo: skrypt cron eksportuje do S3/R2
```

W produkcji rozważ migrację SQLite → Postgres (Neon.tech ma darmowy tier 0.5 GB).
