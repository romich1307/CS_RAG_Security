"""Generación mock o servidor Ollama local activado explícitamente."""
import ipaddress
import json
import os
from urllib.parse import urlparse
from urllib.request import Request, build_opener, HTTPRedirectHandler, ProxyHandler


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('Redirección de proveedor local rechazada')


def generate(messages, hits, provider='mock', seed=42):
    if provider == 'mock':
        return 'MOCK — vista extractiva de prueba; no es una respuesta de LLM.\n' + '\n'.join(
            f"[{h['archivo_pdf']} p. {h['pagina_pdf']}] {h['texto'][:450]}" for h in hits)
    if provider != 'local':
        raise ValueError('Proveedor no admitido')
    url = os.environ.get('RAG_LOCAL_URL', 'http://127.0.0.1:11434/api/chat')
    parsed = urlparse(url)
    # Solo IP loopback literal: evita DNS, destinos remotos y APIs con coste.
    if parsed.scheme != 'http' or not parsed.hostname or not ipaddress.ip_address(parsed.hostname).is_loopback or parsed.username or parsed.password:
        raise ValueError('Se requiere servidor HTTP en IP loopback literal')
    model = os.environ.get('RAG_LOCAL_MODEL')
    if not model:
        raise ValueError('Configura RAG_LOCAL_MODEL; no se descarga ningún modelo automáticamente')
    data = json.dumps({'model': model, 'messages': messages, 'stream': False,
                       'options': {'temperature': 0, 'seed': seed}}).encode()
    opener = build_opener(ProxyHandler({}), NoRedirect())
    with opener.open(Request(url, data=data, headers={'Content-Type': 'application/json'}), timeout=90) as response:
        return json.load(response)['message']['content']
