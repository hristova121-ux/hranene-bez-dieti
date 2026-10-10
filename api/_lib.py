# Общи функции за сървърната част (Vercel, Python): Stripe, имейли, дати.
# Тайните са в променливите на Vercel (Settings → Environment Variables), не в кода:
#   STRIPE_KEY           ограничен ключ rk_live_… (само четене: Payment Links, Checkout Sessions, Customers, Subscriptions, Refunds)
#   STRIPE_WEBHOOK_SECRET whsec_… от Developers → Webhooks
#   GMAIL_USER           hranenebezdieti@gmail.com
#   GMAIL_APP_PASSWORD   паролата за приложения от Google (16 букви)
#   ALEKS_EMAIL          къде идват известията за Алекс (по подразбиране GMAIL_USER)
#   CRON_SECRET          произволен низ; Vercel го праща при всеки дневен старт
#   PLASHTANE            "1" = бутоните на сайта водят към плащане; празно = само формата
#   MATERIALI_URL        линк към материалите (когато са готови); празно = „до 24 часа“
import base64, hashlib, hmac, json, os, smtplib, ssl, time, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone, date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

LINK_29 = 'https://buy.stripe.com/4gM28s3xBbsf4tf2SReAg01'
LINK_39 = 'https://buy.stripe.com/5kQdRagkn7bZ6BnctreAg00'
LINK_19 = 'https://buy.stripe.com/5kQ28s8RV0NBaRD9hfeAg02'
PORTAL = 'https://billing.stripe.com/p/login/5kQdRagkn7bZ6BnctreAg00'
SITE = 'https://hranene-bez-dieti.vercel.app'
MESTA = 30


def env(k, d=''):
    return os.environ.get(k, d).strip()


# ---------- Stripe ----------
def stripe_get(path, params=None):
    q = urllib.parse.urlencode(params or {}, doseq=True)
    r = urllib.request.Request('https://api.stripe.com/v1/' + path + ('?' + q if q else ''),
                               headers={'Authorization': 'Bearer ' + env('STRIPE_KEY')})
    with urllib.request.urlopen(r, timeout=20) as f:
        return json.load(f)


def stripe_all(path, params=None, cap=2000):
    """Всички записи от списък в Stripe (страница по страница)."""
    params = dict(params or {}, limit=100)
    out = []
    while True:
        d = stripe_get(path, params)
        out += d['data']
        if not d.get('has_more') or len(out) >= cap:
            return out
        params['starting_after'] = d['data'][-1]['id']


def verify_webhook(body, header, secret, tolerance=300):
    """Проверка на подписа Stripe-Signature (t=…,v1=…)."""
    try:
        parts = dict(p.split('=', 1) for p in header.split(',') if '=' in p)
        sigs = [p.split('=', 1)[1] for p in header.split(',') if p.startswith('v1=')]
        t = int(parts['t'])
    except Exception:
        return False
    if abs(time.time() - t) > tolerance:
        return False
    exp = hmac.new(secret.encode(), str(t).encode() + b'.' + body, hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(exp, s) for s in sigs)


def oferta():
    """Колко места на 29 € остават (броят на платените през линка за 29 €)."""
    links = stripe_all('payment_links', {'active': 'true'}) + stripe_all('payment_links', {'active': 'false'})
    pl = next((l for l in links if l.get('url') == LINK_29), None)
    if not pl:
        return MESTA
    done = (((pl.get('restrictions') or {}).get('completed_sessions')) or {}).get('count')
    if done is None:
        done = len(stripe_all('checkout/sessions', {'payment_link': pl['id'], 'status': 'complete'}))
    if not pl.get('active'):
        return 0
    return max(0, MESTA - done)


# ---------- дати (България) ----------
def _last_sunday(y, m):
    d = date(y, m + 1, 1) - timedelta(days=1) if m < 12 else date(y, 12, 31)
    return d - timedelta(days=(d.weekday() + 1) % 7)


def to_sofia(ts):
    """UTC секунди → местно време (EET/EEST, лятното часово време по правилата на ЕС)."""
    u = datetime.fromtimestamp(ts, timezone.utc)
    start = datetime.combine(_last_sunday(u.year, 3), datetime.min.time(), timezone.utc) + timedelta(hours=1)
    end = datetime.combine(_last_sunday(u.year, 10), datetime.min.time(), timezone.utc) + timedelta(hours=1)
    return u + timedelta(hours=3 if start <= u < end else 2)


def today_sofia():
    return to_sofia(time.time()).date()


def group_dates(paid_ts):
    """Влизане в групата: първият понеделник СЛЕД покупката. Край: 21 дни по-късно."""
    d = to_sofia(paid_ts).date()
    start = d + timedelta(days=(7 - d.weekday()) or 7)
    return start, start + timedelta(days=21)


MESECI = ['януари', 'февруари', 'март', 'април', 'май', 'юни', 'юли', 'август', 'септември', 'октомври', 'ноември', 'декември']


def bg_date(d):
    return f'{d.day} {MESECI[d.month - 1]}'


# ---------- имейли ----------
def send_mail(to, subject, paragraphs, button=None):
    """Изпраща имейл от Gmail на групата. paragraphs: списък от редове (HTML е позволен)."""
    user, pw = env('GMAIL_USER'), env('GMAIL_APP_PASSWORD').replace(' ', '')
    if not (user and pw and to):
        return False
    btn = ''
    if button:
        btn = (f'<p style="margin:28px 0"><a href="{button[1]}" style="background:#5f7a4f;color:#fff;'
               f'text-decoration:none;padding:14px 26px;border-radius:999px;font-weight:600;display:inline-block">{button[0]}</a></p>')
    body = ''.join(f'<p style="margin:0 0 14px">{p}</p>' for p in paragraphs)
    html = (f'<div style="background:#f8f6f1;padding:28px 16px;font-family:Arial,Helvetica,sans-serif">'
            f'<div style="max-width:560px;margin:0 auto;background:#fff;padding:32px 28px;color:#2f3a2a;font-size:16px;line-height:1.55">'
            f'<p style="margin:0 0 22px;font-size:13px;letter-spacing:.08em;text-transform:uppercase;color:#5f7a4f;font-weight:700">Хранене без диети</p>'
            f'{body}{btn}<p style="margin:26px 0 0">Алекс</p></div>'
            f'<p style="max-width:560px;margin:14px auto 0;font-size:12px;color:#8a8a80;text-align:center">'
            f'Въпроси: <a href="mailto:{user}" style="color:#8a8a80">{user}</a> · '
            f'<a href="{SITE}/obshti-usloviya/" style="color:#8a8a80">Общи условия</a></p></div>')
    text = '\n\n'.join(p.replace('<b>', '').replace('</b>', '').replace('<br>', '\n') for p in paragraphs)
    if button:
        text += f'\n\n{button[0]}: {button[1]}'
    text += '\n\nАлекс'
    m = MIMEMultipart('alternative')
    m['Subject'] = subject
    m['From'] = formataddr(('Хранене без диети', user))
    m['To'] = to
    m['Reply-To'] = user
    m.attach(MIMEText(text, 'plain', 'utf-8'))
    m.attach(MIMEText(html, 'html', 'utf-8'))
    with smtplib.SMTP_SSL('smtp.gmail.com', 465, context=ssl.create_default_context(), timeout=20) as s:
        s.login(user, pw)
        s.sendmail(user, [to], m.as_string())
    return True


def aleks():
    return env('ALEKS_EMAIL') or env('GMAIL_USER')


def esc(s):
    return (s or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def first_name(name):
    return esc((name or '').strip().split(' ')[0]) if name else ''


def link19(email):
    return LINK_19 + ('?prefilled_email=' + urllib.parse.quote(email) if email else '')


def respond(h, code, obj, cache=None):
    b = json.dumps(obj, ensure_ascii=False).encode()
    h.send_response(code)
    h.send_header('Content-Type', 'application/json; charset=utf-8')
    if cache:
        h.send_header('Cache-Control', cache)
    h.end_headers()
    h.wfile.write(b)
