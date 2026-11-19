import io
import json
import urllib.error
import pytest
from cs_rag_security.generation import generate, NoRedirect
from cs_rag_security.pipeline import answer
from cs_rag_security.retrieval import Index


def _mock_http_response(payload, status=200):
    body = json.dumps(payload).encode('utf-8')
    resp = io.BytesIO(body)
    resp.status = status
    resp.code = status
    return resp


def test_api_provider_requires_key_and_model(monkeypatch):
    monkeypatch.delenv('RAG_API_KEY', raising=False)
    monkeypatch.delenv('RAG_API_MODEL', raising=False)
    with pytest.raises(ValueError, match='Configura RAG_API_KEY'):
        generate([], [], provider='api')

    monkeypatch.setenv('RAG_API_KEY', 'test-key')
    with pytest.raises(ValueError, match='Configura RAG_API_MODEL'):
        generate([], [], provider='api')


def test_api_provider_destination_security_and_prevalidation(monkeypatch):
    monkeypatch.setenv('RAG_API_KEY', 'test-key')
    monkeypatch.setenv('RAG_API_MODEL', 'gpt-4o-mini')

    # Esquema inseguro HTTP
    monkeypatch.setenv('RAG_API_URL', 'http://api.openai.com/v1/chat/completions')
    with pytest.raises(ValueError, match='Se requiere conexión HTTPS'):
        generate([], [], provider='api')

    # Dominio no autorizado
    monkeypatch.setenv('RAG_API_URL', 'https://evil.com/v1/chat/completions')
    with pytest.raises(ValueError, match='Destino no autorizado; solo se permite api.openai.com'):
        generate([], [], provider='api')

    # Subdominio engañoso como sufijo
    monkeypatch.setenv('RAG_API_URL', 'https://api.openai.com.attacker.com/v1/chat/completions')
    with pytest.raises(ValueError, match='Destino no autorizado; solo se permite api.openai.com'):
        generate([], [], provider='api')

    # Subdominio engañoso como prefijo
    monkeypatch.setenv('RAG_API_URL', 'https://fakeapi.openai.com/v1/chat/completions')
    with pytest.raises(ValueError, match='Destino no autorizado; solo se permite api.openai.com'):
        generate([], [], provider='api')

    # Puertos no permitidos
    monkeypatch.setenv('RAG_API_URL', 'https://api.openai.com:8443/v1/chat/completions')
    with pytest.raises(ValueError, match='Solo se permite el puerto estándar HTTPS \\(443\\)'):
        generate([], [], provider='api')

    monkeypatch.setenv('RAG_API_URL', 'https://api.openai.com:80/v1/chat/completions')
    with pytest.raises(ValueError, match='Solo se permite el puerto estándar HTTPS \\(443\\)'):
        generate([], [], provider='api')

    # Credenciales en la URL
    monkeypatch.setenv('RAG_API_URL', 'https://user:pass@api.openai.com/v1/chat/completions')
    with pytest.raises(ValueError, match='URL de API remota no debe contener credenciales'):
        generate([], [], provider='api')


def test_api_provider_validation_happens_before_network(monkeypatch):
    monkeypatch.setenv('RAG_API_KEY', 'test-key')
    monkeypatch.setenv('RAG_API_MODEL', 'gpt-4o-mini')
    monkeypatch.setenv('RAG_API_URL', 'https://unauthorized-destination.com/v1/chat/completions')

    class ShouldNotBeCalledOpener:
        def open(self, req, timeout=60):
            raise AssertionError('No debe intentarse ninguna conexión de red ante URL inválida')

    import cs_rag_security.generation as gen_mod
    monkeypatch.setattr(gen_mod, 'build_opener', lambda *a, **kw: ShouldNotBeCalledOpener())

    with pytest.raises(ValueError, match='Destino no autorizado'):
        generate([], [], provider='api')


def test_api_provider_noredirect_handler():
    handler = NoRedirect()
    with pytest.raises(ValueError, match='Redirección de proveedor rechazada'):
        handler.redirect_request(None, None, 301, 'Moved Permanently', {}, 'https://api.openai.com/other')


def test_api_provider_mock_call_success_and_metadata(monkeypatch):
    test_key = 'sk-test-secret-key-12345'
    monkeypatch.setenv('RAG_API_KEY', test_key)
    monkeypatch.setenv('RAG_API_MODEL', 'gpt-4o-mini')
    monkeypatch.setenv('RAG_API_URL', 'https://api.openai.com:443/v1/chat/completions')

    captured_requests = []

    class MockOpener:
        def open(self, req, timeout=60):
            captured_requests.append(req)
            payload = {
                'id': 'chatcmpl-test',
                'model': 'gpt-4o-mini-2024-07-18',
                'system_fingerprint': 'fp_test_abc',
                'choices': [
                    {'message': {'role': 'assistant', 'content': 'Respuesta con [doc.pdf p. 1]'}}
                ],
                'usage': {
                    'prompt_tokens': 120,
                    'completion_tokens': 30,
                    'total_tokens': 150
                }
            }
            return _mock_http_response(payload)

    import cs_rag_security.generation as gen_mod
    monkeypatch.setattr(gen_mod, 'build_opener', lambda *a, **kw: MockOpener())

    messages = [{'role': 'user', 'content': 'pregunta'}]
    res = generate(messages, [], provider='api', seed=42, return_metadata=True)

    assert isinstance(res, dict)
    assert res['text'] == 'Respuesta con [doc.pdf p. 1]'
    meta = res['metadata']
    assert meta['provider'] == 'api'
    assert meta['model'] == 'gpt-4o-mini-2024-07-18'
    assert meta['parameters'] == {'temperature': 0, 'seed': 42}
    assert meta['system_fingerprint'] == 'fp_test_abc'
    assert meta['usage'] == {'prompt_tokens': 120, 'completion_tokens': 30, 'total_tokens': 150}
    assert 'latency_seconds' in meta and meta['latency_seconds'] >= 0

    assert len(captured_requests) == 1
    req = captured_requests[0]
    assert req.headers.get('Authorization') == f'Bearer {test_key}'
    body_data = json.loads(req.data.decode('utf-8'))
    assert body_data['model'] == 'gpt-4o-mini'
    assert body_data['temperature'] == 0
    assert body_data['seed'] == 42


def test_api_provider_omitted_usage_not_invented(monkeypatch):
    monkeypatch.setenv('RAG_API_KEY', 'test-key')
    monkeypatch.setenv('RAG_API_MODEL', 'gpt-4o-mini')

    class MockOpener:
        def open(self, req, timeout=60):
            payload = {
                'id': 'chatcmpl-test',
                'choices': [{'message': {'role': 'assistant', 'content': 'Texto'}}]
            }
            return _mock_http_response(payload)

    import cs_rag_security.generation as gen_mod
    monkeypatch.setattr(gen_mod, 'build_opener', lambda *a, **kw: MockOpener())

    res = generate([{'role': 'user', 'content': 'test'}], [], provider='api', return_metadata=True)
    assert 'usage' not in res['metadata']
    assert 'system_fingerprint' not in res['metadata']


def test_api_provider_sanitized_errors_no_reason_leakage(monkeypatch):
    secret_key = 'super-secret-key-to-hide'
    monkeypatch.setenv('RAG_API_KEY', secret_key)
    monkeypatch.setenv('RAG_API_MODEL', 'gpt-4o-mini')

    # Caso 1: HTTPError no expone exc.reason ni headers ni key
    class FailingHttpOpener:
        def open(self, req, timeout=60):
            raise urllib.error.HTTPError(req.full_url, 401, 'Unauthorized sensitive reason detail', {}, None)

    import cs_rag_security.generation as gen_mod
    monkeypatch.setattr(gen_mod, 'build_opener', lambda *a, **kw: FailingHttpOpener())

    with pytest.raises(RuntimeError) as exc_http:
        generate([{'role': 'user', 'content': 'hola'}], [], provider='api')
    err_str = str(exc_http.value)
    assert err_str == 'Error HTTP del proveedor API (401)'
    assert secret_key not in err_str
    assert 'sensitive reason detail' not in err_str

    # Caso 2: URLError genérico no expone detalles internos
    class FailingUrlOpener:
        def open(self, req, timeout=60):
            raise urllib.error.URLError('internal-network-error-detail')

    monkeypatch.setattr(gen_mod, 'build_opener', lambda *a, **kw: FailingUrlOpener())

    with pytest.raises(RuntimeError) as exc_url:
        generate([{'role': 'user', 'content': 'hola'}], [], provider='api')
    err_str_url = str(exc_url.value)
    assert err_str_url == 'Error de conexión con el proveedor API'
    assert 'internal-network-error-detail' not in err_str_url
    assert secret_key not in err_str_url


def test_local_provider_latency_measured_with_metadata(monkeypatch):
    monkeypatch.setenv('RAG_LOCAL_MODEL', 'llama3')
    payload = {'message': {'content': 'Respuesta local [RCU-0161-2021.pdf p. 1]'}}

    class MockLocalOpener:
        def open(self, req, timeout=90):
            return _mock_http_response(payload)

    import cs_rag_security.generation as gen_mod
    monkeypatch.setattr(gen_mod, 'build_opener', lambda *a, **kw: MockLocalOpener())

    res = generate([{'role': 'user', 'content': 'pregunta'}], [], provider='local', return_metadata=True)
    assert isinstance(res, dict)
    assert 'latency_seconds' in res['metadata']
    assert res['metadata']['latency_seconds'] >= 0
    assert res['metadata']['provider'] == 'local'
    assert res['metadata']['model'] == 'llama3'


def test_pipeline_integration_with_api_provider(monkeypatch):
    import cs_rag_security.pipeline as pipeline
    hit = {
        'chunk_id': 'test:1', 'archivo_pdf': 'demo.pdf', 'pagina_pdf': 1,
        'texto': 'Evaluación académica', 'ocr_revision_manual_pendiente': False,
        'normativa_actual_verificada': False, 'score': 1.0
    }
    idx = Index([hit])

    # Respuesta válida con cita del contexto
    monkeypatch.setattr(pipeline, 'generate', lambda *a: {
        'text': 'Según la norma [demo.pdf p. 1] se evalúa.',
        'metadata': {'provider': 'api', 'model': 'gpt-4o-mini', 'usage': {'total_tokens': 50}}
    })
    res_ok = answer(idx, 'evaluación', provider='api', documental=True)
    assert not res_ok['abstained']
    assert res_ok['provider'] == 'api'
    assert res_ok['generation_metadata']['model'] == 'gpt-4o-mini'

    # Respuesta inválida con cita inventada -> abstención obligatoria
    monkeypatch.setattr(pipeline, 'generate', lambda *a: {
        'text': 'Según [inventado.pdf p. 99] todo cambia.',
        'metadata': {'provider': 'api', 'model': 'gpt-4o-mini'}
    })
    res_bad = answer(idx, 'evaluación', provider='api', documental=True)
    assert res_bad['abstained']
    assert 'carece de citas válidas' in res_bad['response']
