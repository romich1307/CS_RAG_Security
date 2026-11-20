"""Generación mock, servidor Ollama local o proveedor API OpenAI-compatible."""
import ipaddress
import json
import os
import time
import urllib.error
from urllib.parse import urlparse
from urllib.request import Request, build_opener, HTTPRedirectHandler, ProxyHandler


ALLOWED_API_HOST = 'api.openai.com'


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('Redirección de proveedor rechazada')


def generate(messages, hits, provider='mock', seed=42, return_metadata=False):
    if provider == 'mock':
        text = 'MOCK — vista extractiva de prueba; no es una respuesta de LLM.\n' + '\n'.join(
            f"[{h['archivo_pdf']} p. {h['pagina_pdf']}] {h['texto'][:450]}" for h in hits)
        if return_metadata:
            return {'text': text, 'metadata': {'provider': 'mock', 'model': 'mock_extractivo_v1', 'parameters': {'seed': seed}}}
        return text

    if provider == 'local':
        url = os.environ.get('RAG_LOCAL_URL', 'http://127.0.0.1:11434/api/chat')
        parsed = urlparse(url)
        # Solo IP loopback literal: evita DNS, destinos remotos y APIs con coste.
        if parsed.scheme != 'http' or not parsed.hostname or not ipaddress.ip_address(parsed.hostname).is_loopback or parsed.username or parsed.password:
            raise ValueError('Se requiere servidor HTTP en IP loopback literal')
        model = os.environ.get('RAG_LOCAL_MODEL')
        if not model:
            raise ValueError('Configura RAG_LOCAL_MODEL; no se descarga ningún modelo automáticamente')
        data = json.dumps({'model': model, 'messages': messages, 'stream': False,
                           'options': {'temperature': 0, 'seed': seed}}).encode('utf-8')
        opener = build_opener(ProxyHandler({}), NoRedirect())
        start_t = time.perf_counter()
        with opener.open(Request(url, data=data, headers={'Content-Type': 'application/json'}), timeout=90) as response:
            body = json.load(response)
            latency = time.perf_counter() - start_t
            msg = body.get('message') or {}
            raw_content = msg.get('content')
            text = raw_content if isinstance(raw_content, str) else ''
            if return_metadata:
                metadata = {
                    'provider': 'local',
                    'model': body.get('model') or model,
                    'parameters': {'temperature': 0, 'seed': seed},
                    'latency_seconds': latency,
                    'latency': latency
                }
                return {'text': text, 'metadata': metadata}
            return text

    if provider == 'api':
        api_key = os.environ.get('RAG_API_KEY')
        if not api_key:
            raise ValueError('Configura RAG_API_KEY para el proveedor api')
        model = os.environ.get('RAG_API_MODEL')
        if not model:
            raise ValueError('Configura RAG_API_MODEL para el proveedor api')
        url = os.environ.get('RAG_API_URL', 'https://api.openai.com/v1/chat/completions')
        parsed = urlparse(url)
        if parsed.scheme != 'https':
            raise ValueError('Se requiere conexión HTTPS para el proveedor remoto')
        if parsed.username or parsed.password:
            raise ValueError('URL de API remota no debe contener credenciales')
        if (parsed.hostname or '').lower() != ALLOWED_API_HOST:
            raise ValueError(f'Destino no autorizado; solo se permite {ALLOWED_API_HOST}')
        if parsed.port not in (None, 443):
            raise ValueError('Solo se permite el puerto estándar HTTPS (443)')

        timeout = int(os.environ.get('RAG_API_TIMEOUT', '60'))
        data = json.dumps({
            'model': model,
            'messages': messages,
            'temperature': 0,
            'seed': seed
        }).encode('utf-8')
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}',
            'User-Agent': 'CS_RAG_Security/0.1.0'
        }
        opener = build_opener(ProxyHandler({}), NoRedirect())
        req = Request(url, data=data, headers=headers)
        start_t = time.perf_counter()
        try:
            with opener.open(req, timeout=timeout) as response:
                body = json.load(response)
                latency = time.perf_counter() - start_t
        except urllib.error.HTTPError as exc:
            # Nunca exponer la API key, headers ni exc.reason en el mensaje de excepción
            raise RuntimeError(f'Error HTTP del proveedor API ({exc.code})') from None
        except urllib.error.URLError:
            raise RuntimeError('Error de conexión con el proveedor API') from None

        choices = body.get('choices')
        if not choices or not isinstance(choices, list):
            raise ValueError('Formato de respuesta no reconocido del proveedor API')
        first_choice = choices[0] if isinstance(choices[0], dict) else {}
        message = first_choice.get('message')
        if not isinstance(message, dict):
            message = {}
        raw_content = message.get('content')
        refusal = message.get('refusal') or first_choice.get('refusal')
        finish_reason = first_choice.get('finish_reason')
        if isinstance(raw_content, str):
            text = raw_content
        elif isinstance(refusal, str):
            text = refusal
        else:
            text = ''
        if return_metadata:
            metadata = {
                'provider': 'api',
                'model': body.get('model') or model,
                'parameters': {'temperature': 0, 'seed': seed},
                'latency_seconds': latency,
                'latency': latency
            }
            if body.get('system_fingerprint'):
                metadata['system_fingerprint'] = body['system_fingerprint']
            if finish_reason:
                metadata['finish_reason'] = finish_reason
            if refusal:
                metadata['refusal'] = refusal
            usage = body.get('usage')
            if isinstance(usage, dict):
                tokens_data = {
                    k: usage[k] for k in ('prompt_tokens', 'completion_tokens', 'total_tokens')
                    if k in usage and isinstance(usage[k], (int, float))
                }
                metadata['usage'] = tokens_data
                metadata['tokens'] = tokens_data
            return {'text': text, 'metadata': metadata}
        return text

    raise ValueError('Proveedor no admitido')
