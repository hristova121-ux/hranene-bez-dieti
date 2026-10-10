# ВРЕМЕННО: проверка дали Vercel стига до smtp.gmail.com (без пароли, без ключове). Да се изтрие.
import json, smtplib, ssl
from http.server import BaseHTTPRequestHandler


def probe(port):
    try:
        if port == 465:
            s = smtplib.SMTP_SSL('smtp.gmail.com', 465, context=ssl.create_default_context(), timeout=15)
        else:
            s = smtplib.SMTP('smtp.gmail.com', port, timeout=15)
            s.ehlo()
            s.starttls(context=ssl.create_default_context())
        code = s.ehlo()[0]
        s.quit()
        return 'ok %s' % code
    except Exception as e:
        return '%s: %s' % (type(e).__name__, e)


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        b = json.dumps({'465': probe(465), '587': probe(587)}).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(b)
