# GET /api/oferta → колко места на 29 € остават и кой линк за плащане важи.
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from http.server import BaseHTTPRequestHandler
import _lib as L


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        on = L.env('PLASHTANE') == '1' and bool(L.env('STRIPE_KEY'))
        try:
            ostavat = L.oferta() if L.env('STRIPE_KEY') else L.MESTA
        except Exception:
            ostavat = None  # Stripe не отговори: сайтът остава на 29 € (линкът сам се спира след 30)
        L.respond(self, 200, {
            'plashtane': on,
            'ostavat': ostavat,
            'cena': 39 if ostavat == 0 else 29,
            'link': L.LINK_39 if ostavat == 0 else L.LINK_29,
        }, cache='public, s-maxage=30, stale-while-revalidate=60')
