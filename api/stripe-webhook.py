# POST /api/stripe-webhook ← Stripe (Developers → Webhooks), събития:
#   checkout.session.completed   плащане на програмата или абонамента
#   customer.subscription.deleted абонаментът е спрян (от клиентката или поради неплащане)
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from http.server import BaseHTTPRequestHandler
import _lib as L


def platena_programa(s):
    c = s.get('customer_details') or {}
    email, name, phone = c.get('email'), c.get('name'), c.get('phone')
    start, end = L.group_dates(s['created'])
    mat = L.env('MATERIALI_URL')
    ime = L.first_name(name)
    L.send_mail(email, 'Добре дошла в „Хранене без диети“', [
        f'Здравей{", " + ime if ime else ""}!',
        'Благодаря ти, че избра „Хранене без диети“. Плащането е получено.',
        ('Материалите са на линка по-долу и остават твои завинаги.' if mat else
         'Материалите ще получиш на този имейл до 24 часа.'),
        f'В понеделник, <b>{L.bg_date(start)}</b>, ще те добавим в закритата Viber група по номера, който посочи ({L.esc(phone)}). '
        f'Там получаваш ексклузивно съдържание, а всеки вторник разглеждам чиниите ти и ти давам съвети. 21-те дни в групата са до <b>{L.bg_date(end - L.timedelta(days=1))}</b>.',
        'Ако номерът ти за Viber е различен, просто отговори на този имейл.',
    ], button=('Към материалите', mat) if mat else None)
    L.send_mail(L.aleks(), f'Нова продажба: {name or email} ({(s.get("amount_total") or 0) / 100:.0f} €)', [
        f'<b>{L.esc(name)}</b><br>{L.esc(email)}<br>Телефон: <b>{L.esc(phone)}</b>',
        f'Добави я във Viber групата в понеделник, {L.bg_date(start)}. 21-те дни свършват на {L.bg_date(end - L.timedelta(days=1))}.',
        ('Материалите ѝ бяха изпратени автоматично.' if mat else '<b>Изпрати ѝ материалите до 24 часа.</b>'),
    ])


def nov_abonament(s):
    c = s.get('customer_details') or {}
    email, name, phone = c.get('email'), c.get('name'), c.get('phone')
    ime = L.first_name(name)
    L.send_mail(email, 'Оставаш в групата', [
        f'Здравей{", " + ime if ime else ""}!',
        'Супер, че оставаш! Абонаментът ти от 19 € на месец е активен и продължаваш да получаваш ексклузивното съдържание и съветите за чиниите си във Viber групата.',
        'Абонаментът се подновява автоматично всеки месец. 3 дни преди всяко плащане ще получиш напомняне. Можеш да го спреш по всяко време от линка по-долу (влизаш с този имейл).',
    ], button=('Управление на абонамента', L.PORTAL))
    L.send_mail(L.aleks(), f'Нов абонамент: {name or email}', [
        f'<b>{L.esc(name)}</b><br>{L.esc(email)}<br>Телефон: <b>{L.esc(phone)}</b>',
        'Остава в групата след 21-те дни. Не я изваждай.',
    ])


def sprian_abonament(sub):
    try:
        cu = L.stripe_get('customers/' + sub['customer'])
    except Exception:
        cu = {}
    email, name, phone = cu.get('email'), cu.get('name'), cu.get('phone')
    neplateno = ((sub.get('cancellation_details') or {}).get('reason')) == 'payment_failed'
    ime = L.first_name(name)
    if neplateno:
        L.send_mail(email, 'Абонаментът ти е прекратен', [
            f'Здравей{", " + ime if ime else ""}!',
            'Не успяхме да таксуваме картата ти за месечния абонамент, затова той е прекратен поради неплащане и излизаш от Viber групата. Материалите остават твои.',
            'Ако искаш да се върнеш, можеш да се абонираш отново по всяко време.',
        ], button=('Абонирай се отново', L.link19(email)))
    else:
        L.send_mail(email, 'Абонаментът ти е спрян', [
            f'Здравей{", " + ime if ime else ""}!',
            'Абонаментът ти е спрян и няма да бъдеш таксувана повече. Излизаш от Viber групата, а материалите остават твои.',
            'Благодаря ти, че беше с нас! Ако решиш да се върнеш, вратата е отворена.',
        ], button=('Абонирай се отново', L.link19(email)))
    L.send_mail(L.aleks(), f'Извади от групата: {name or email}', [
        f'<b>{L.esc(name)}</b><br>{L.esc(email)}<br>Телефон: <b>{L.esc(phone)}</b>',
        'Абонаментът е ' + ('прекратен поради неплащане.' if neplateno else 'спрян от нея.') + ' Извади я от Viber групата.',
    ])


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        body = self.rfile.read(int(self.headers.get('Content-Length') or 0))
        if not L.verify_webhook(body, self.headers.get('Stripe-Signature', ''), L.env('STRIPE_WEBHOOK_SECRET')):
            return L.respond(self, 400, {'error': 'bad signature'})
        ev = json.loads(body)
        o = ev['data']['object']
        try:
            if ev['type'] == 'checkout.session.completed' and o.get('payment_status') in ('paid', 'no_payment_required'):
                (nov_abonament if o.get('mode') == 'subscription' else platena_programa)(o)
            elif ev['type'] == 'customer.subscription.deleted':
                sprian_abonament(o)
        except Exception as e:
            # 500 → Stripe опитва пак по-късно
            return L.respond(self, 500, {'error': str(e)})
        L.respond(self, 200, {'ok': True})
