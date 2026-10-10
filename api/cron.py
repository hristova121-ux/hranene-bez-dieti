# GET /api/cron — пуска се от Vercel всеки ден (vercel.json). Праща:
#   на клиентките: покана за абонамента 5, 3 и 1 ден преди края на 21-те дни (ако още нямат абонамент)
#   на Алекс: в понеделник — кого да добави в групата; в деня след края — кого да извади
import os, sys, time
sys.path.insert(0, os.path.dirname(__file__))
from http.server import BaseHTTPRequestHandler
from datetime import timedelta
import _lib as L


def run(today=None, dry=False):
    today = today or L.today_sofia()
    since = int(time.time()) - 45 * 86400
    sessions = [s for s in L.stripe_all('checkout/sessions', {'status': 'complete', 'created[gte]': since})
                if s.get('mode') == 'payment' and s.get('payment_status') == 'paid']
    refunded = {r.get('payment_intent') for r in L.stripe_all('refunds', {'created[gte]': since})}
    subs = L.stripe_all('subscriptions', {'status': 'all', 'expand[]': 'data.customer'})
    abonirani = {((x.get('customer') or {}).get('email') or '').lower()
                 for x in subs if x.get('status') in ('active', 'trialing', 'past_due')}
    log, dobavi, izvadi = [], [], []
    for s in sessions:
        if s.get('payment_intent') in refunded:
            continue
        c = s.get('customer_details') or {}
        email, name, phone = c.get('email') or '', c.get('name') or '', c.get('phone') or ''
        start, end = L.group_dates(s['created'])
        last = end - timedelta(days=1)  # последният ден в групата (неделя)
        left = (last - today).days
        has_sub = email.lower() in abonirani
        if start == today:
            dobavi.append((name, email, phone))
        if today == end and not has_sub:
            izvadi.append((name, email, phone))
        if left in (5, 3, 1) and not has_sub:
            log.append(('покана', left, email))
            if not dry:
                ime = L.first_name(name)
                kraj = L.bg_date(last)
                koga = {5: 'след 5 дни', 3: 'след 3 дни', 1: 'утре'}[left]
                L.send_mail(email, f'Твоите 21 дни в групата свършват {koga}', [
                    f'Здравей{", " + ime if ime else ""}!',
                    f'Твоите 21 дни в закритата Viber група свършват {koga} ({kraj}). Материалите остават твои завинаги.',
                    'Ако искаш да продължиш да получаваш ексклузивното съдържание и съветите ми за чиниите си, можеш да останеш в групата с абонамент от <b>19 € на месец</b>.',
                    'Абонаментът се подновява автоматично всеки месец, 3 дни преди всяко плащане получаваш напомняне и можеш да го спреш по всяко време.',
                ], button=('Искам да остана в групата', L.link19(email)))
    def spisak(xs):
        return '<br>'.join(f'<b>{L.esc(n)}</b> · {L.esc(p)} · {L.esc(e)}' for n, e, p in xs)
    if dobavi and not dry:
        L.send_mail(L.aleks(), f'Днес добави в групата: {len(dobavi)}', ['Добави във Viber групата:', spisak(dobavi)])
    if izvadi and not dry:
        L.send_mail(L.aleks(), f'Днес извади от групата: {len(izvadi)}', ['21-те дни свършиха и нямат абонамент. Извади ги от Viber групата:', spisak(izvadi)])
    return {'den': str(today), 'pokani': log, 'dobavi': len(dobavi), 'izvadi': len(izvadi)}


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.headers.get('Authorization') != 'Bearer ' + L.env('CRON_SECRET') or not L.env('CRON_SECRET'):
            return L.respond(self, 401, {'error': 'unauthorized'})
        try:
            L.respond(self, 200, run())
        except Exception as e:
            L.respond(self, 500, {'error': str(e)})
