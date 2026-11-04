"""Consumidor independente do contrato de sinal v1: prova o contrato so com o texto, o schema e os exemplos.
Rodar: python3 infra/tests/test-signal-contract-v1-consumer.py  (tambem coletavel pelo pytest)."""
import copy
from fractions import Fraction
import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXAMPLES = HERE.parents[1] / 'docs/specs/examples/signal-v1'
spec = importlib.util.spec_from_file_location('signal_v1_consumer', HERE / 'signal_v1_consumer.py')
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)


def ex(name):
    return json.loads((EXAMPLES / f'{name}.json').read_text(encoding='utf-8'))


def errs(doc, stored=False):
    return c.validate(doc, stored=stored)[0]


def has(doc, text):
    return any(text in e for e in errs(doc))


def has_s(doc, text):
    return any(text in e for e in errs(doc, stored=True))

def ot_with_payload(payload):
    d = ex('ot-batch')
    d['payload'] = payload
    d['batch']['integrity']['digest'] = c.payload_digest(payload)
    return d


def test_a_official_examples_accepted():
    names = sorted(p.stem for p in EXAMPLES.glob('*.json'))
    assert names == ['cloud-event', 'cloud-event-stored', 'ot-batch', 'ot-batch-stored', 'wazuh-alert',
                     'wazuh-alert-stored', 'wazuh-pending-tenant'], names
    for n in names:
        stored = n.endswith('-stored')
        assert errs(ex(n), stored=stored) == [], (n, errs(ex(n), stored=stored))
        if stored:  # registro armazenado traz tenant_id preenchido: na entrada seria rejeitado
            assert has(ex(n), 'tenant_id preenchido'), n
        else:
            assert ex(n)['tenant_id'] is None
    # entrada e registro diferem so no tenant_id (e o registro tem o valor do vinculo)
    for n in ('cloud-event', 'ot-batch', 'wazuh-alert'):
        a, b = ex(n), ex(n + '-stored')
        assert {**a, 'tenant_id': b['tenant_id']} == b, n


def test_b_input_with_tenant_is_rejected_and_hub_fills_the_record():
    doc = ex('wazuh-alert')
    assert doc['tenant_id'] is None and errs(doc) == []
    # entrada com tenant_id preenchido: REJEITADA com campo, valor e id
    forged = {**doc, 'tenant_id': 'tenant-forjado'}
    e = errs(forged)
    assert len(e) == 1 and 'tenant_id' in e[0] and 'tenant-forjado' in e[0] and doc['source_id'] in e[0] \
        and doc['event_id'] in e[0], e
    try:
        c.ingest(forged, lambda s: 'tenant-vinculado', '2026-11-04T13:15:32Z')
        raise AssertionError('deveria rejeitar')
    except ValueError:
        pass
    # tenant_id ausente na entrada: aceito (equivale a null)
    absent = {k: v for k, v in doc.items() if k != 'tenant_id'}
    assert errs(absent) == []
    # o Hub preenche o registro armazenado; received_at da origem e substituido
    absent['received_at'] = '2000-01-01T00:00:00Z'
    r = c.ingest(absent, lambda s: 'tenant-vinculado', '2026-11-04T13:15:32Z')
    assert r['record']['tenant_id'] == 'tenant-vinculado' and not r['pending_tenant_review']
    assert r['record']['received_at'] == '2026-11-04T13:15:32Z'
    assert errs(r['record'], stored=True) == []
    # sem vinculo (ou vinculos conflitantes) -> pendente, nunca 'default'
    r = c.ingest(doc, lambda s: None, '2026-11-04T13:15:32Z')
    assert r['record']['tenant_id'] is None and r['pending_tenant_review']
    # registro armazenado: tenant_id obrigatorio, texto nao vazio ou null
    stored = ex('wazuh-alert-stored')
    del stored['tenant_id']
    assert has_s(stored, 'obrigatorio')
    stored['tenant_id'] = ''
    assert has_s(stored, 'tenant_id')
    stored['tenant_id'] = 7
    assert has_s(stored, 'tenant_id')
    stored['tenant_id'] = None  # pendente de vinculo
    assert errs(stored, stored=True) == []

def test_b2_idempotency_key_has_no_tenant_and_conflict_is_recorded():
    a = c.ingest(ex('wazuh-alert'), lambda s: None, '2026-11-04T13:15:32Z')['record']  # pendente
    assert c.idempotency_key(a) == ('wazuh-manager-sintetico-01', '1762250130.123456')
    # vinculo chega depois: mesma chave, nao duplica
    linked = {**a, 'tenant_id': 'tenant-sintetico-001'}
    assert c.idempotency_key(linked) == c.idempotency_key(a)
    s = c.Store()
    assert s.put(a) == 'new' and s.put(linked) == 'duplicate' and s.put(a) == 'duplicate'
    # mesma chave + payload diferente: conflito registrado, nao sobrescreve
    other = copy.deepcopy(a)
    other['payload']['rule']['level'] = 3
    assert s.put(other) == 'conflict' and len(s.conflicts) == 1
    assert s.records[c.idempotency_key(a)]['payload']['rule']['level'] == 12
    # lote: (source_id, batch_id); sem event_id nao ha deduplicacao
    ot = ex('ot-batch-stored')
    assert c.idempotency_key(ot) == ('ot-probe-sintetica-01', ot['batch']['batch_id'])
    d = ex('cloud-event')
    del d['event_id']
    assert c.idempotency_key(d) is None
    s2 = c.Store()
    assert s2.put(d) == 'new' and s2.put(d) == 'new'

def test_b3_clock_skew_derived_from_record():
    r = c.ingest(ex('wazuh-alert'), lambda s: None, '2026-11-04T13:15:32.480Z')['record']
    assert c.clock_skew(r) == Fraction(148, 100)  # 13:15:32.480Z - 10:15:31-03:00

def test_c_instants_need_explicit_timezone():
    bad = ['2026-11-04T10:00:00', '2026-11-04T10:00:00+0300', '2026-11-04', '2026-11-04T10:00:00+03',
           '2026-11-04 10:00:00Z', '2026-11-04T10:00Z', '2026-13-04T10:00:00Z', '2026-11-04T10:00:00+25:00',
           '', None, 1762250130]
    for field in ('occurred_at', 'collected_at', 'received_at'):
        for v in bad:
            d = ex('wazuh-alert')
            d[field] = v
            assert has(d, field), (field, v)
        for v in ('2026-11-04T10:00:00Z', '2026-11-04T10:00:00.5-03:00', '2026-11-04T10:00:00+05:30'):
            d = ex('wazuh-alert')
            d[field] = v
            assert not has(d, field), (field, v)
    d = ot_with_payload({'a': 1})
    d['batch']['interval']['end'] = '2026-11-04T06:00:00'
    assert has(d, 'interval')


def test_c3_fractional_seconds_are_not_truncated():
    # RFC 3339 admite fracao com qualquer numero de digitos: 7 digitos distinguem start de end
    d = ot_with_payload({'a': 1})
    d['batch']['interval'] = {'start': '2026-11-03T09:00:00.0000001Z', 'end': '2026-11-03T09:00:00.0000002Z'}
    assert not has(d, 'interval')
    d['batch']['interval']['end'] = d['batch']['interval']['start']
    assert has(d, 'start deve ser < end')
    d['batch']['interval']['end'] = '2026-11-03T09:00:00.00000010Z'  # 0,1 us == 0,10 us: igual
    assert has(d, 'start deve ser < end')
    # mesmo instante com fusos diferentes e fracoes de tamanhos diferentes
    assert c.parse_instant('2026-11-04T10:00:00.5-03:00') == c.parse_instant('2026-11-04T13:00:00.500Z')

def test_c2_clock_skew_is_not_rejected():
    d = ex('wazuh-alert')
    d['occurred_at'], d['received_at'] = '2026-11-05T00:00:00Z', '2026-11-01T00:00:00Z'
    errors, warnings = c.validate(d)
    assert errors == [] and warnings


def test_d_compatibility():
    d = ex('wazuh-alert')
    d['schema_version'] = '1.1'
    d['campo_novo'] = {'x': 1}
    d['severity_source']['extra'] = True
    assert errs(d) == []
    r = c.ingest(d, lambda s: 't', '2026-11-04T13:15:32Z')
    assert 'campo_novo' in r['ignored'] and 'campo_novo' not in r['record']
    r = c.ingest(d, lambda s: 't', '2026-11-04T13:15:32Z')  # v1.0 aceita 1.1
    assert r['record']['schema_version'] == '1.1'
    for v in ('2.0', '0.9', '10.0'):
        d['schema_version'] = v
        assert has(d, 'major') or has(d, 'schema_version'), v
    d['schema_version'] = '2.0'
    assert has(d, 'major incompativel')
    for v in ('1', '1.', '1.x', 1.0, None, 'v1.0', '1.01'):
        d['schema_version'] = v
        assert has(d, 'schema_version'), v


def test_e_ot_batch_rules():
    d = ex('ot-batch')
    del d['batch']
    assert has(d, 'batch obrigatorio')
    for n in ('wazuh-alert', 'cloud-event', 'wazuh-pending-tenant'):
        d = ex(n)
        d['batch'] = copy.deepcopy(ex('ot-batch')['batch'])
        assert has(d, 'batch proibido'), n
    for key in ('batch_id', 'rules_version', 'interval', 'integrity'):
        d = ex('ot-batch')
        del d['batch'][key]
        assert errs(d), key
    d = ex('ot-batch')
    d['batch']['interval']['start'], d['batch']['interval']['end'] = (
        d['batch']['interval']['end'], d['batch']['interval']['start'])
    assert has(d, 'start deve ser < end')
    d = ex('ot-batch')
    d['batch']['interval']['end'] = d['batch']['interval']['start']
    assert has(d, 'start deve ser < end')
    d = ex('ot-batch')
    d['batch']['integrity']['algorithm'] = 'sha1'
    assert has(d, 'algorithm')
    d = ex('ot-batch')
    d['batch']['integrity']['digest'] = d['batch']['integrity']['digest'].upper()
    assert has(d, 'hex minusculo')
    d = ex('ot-batch')
    del d['batch']['integrity']['event_count']  # opcional
    assert errs(d) == []


def test_e_digest_is_rfc8785_not_language_default():
    d = ex('ot-batch')
    assert d['batch']['integrity']['digest'] == c.payload_digest(d['payload'])
    # forma canonica escrita a mao: chaves ordenadas, sem espaco, UTF-8 sem escape de nao-ASCII
    payload = {'b': 1, 'a': 'é', 'c': ['x', 2, None, True]}
    canonical = '{"a":"é","b":1,"c":["x",2,null,true]}'
    assert c.jcs(payload) == canonical
    assert c.payload_digest(payload) == hashlib.sha256(canonical.encode('utf-8')).hexdigest()
    naive = hashlib.sha256(json.dumps(payload).encode()).hexdigest()  # serializacao padrao != JCS
    assert c.payload_digest(payload) != naive
    # ordem das chaves por unidade UTF-16 (U+1F600 = D83D DE00 < U+FF5E), nao por code point
    assert c.jcs({'\uff5e': 1, '\U0001f600': 2}) == '{"\U0001f600":2,"\uff5e":1}'
    # escapes minimos do JCS
    assert c.jcs({'k': 'a"b\\c\n\x01/'}) == '{"k":"a\\"b\\\\c\\n\\u0001/"}'
    # digest errado e rejeitado; payload alterado invalida o digest
    d = ex('ot-batch')
    d['payload']['events'][0]['rule']['level'] = 10
    assert has(d, 'nao confere')
    assert errs(ot_with_payload(payload)) == []
    # reordenar chaves do payload nao muda o digest (e canonico)
    assert errs({**ot_with_payload(payload), 'payload': {'c': ['x', 2, None, True], 'a': 'é', 'b': 1}}) == []


def test_e_payload_outside_integer_string_subset_is_flagged_not_crashing():
    d = ot_with_payload({'a': 1})
    for bad in ({'a': 1.5}, {'a': 2 ** 60}, {'a': -2 ** 53}, {'a': ['\ud800']}, {'\udfff': 1}):
        d['payload'] = bad  # float, inteiro fora de +-(2^53-1), surrogate isolado: REJEITADO
        assert has(d, 'subconjunto JCS'), bad
    d['payload'] = {'a': 2 ** 53 - 1, 'b': -(2 ** 53 - 1)}  # limite da faixa segura: ok
    d['batch']['integrity']['digest'] = c.payload_digest(d['payload'])
    assert errs(d) == []
    # chave duplicada no JSON de entrada e rejeitada no parse
    try:
        c.load('{"a": 1, "a": 2}')
        raise AssertionError('deveria rejeitar')
    except ValueError:
        pass
    # instantes dentro do payload nao sao validados pelo envelope (isentos)
    d = ot_with_payload({'timestamp': '2026-11-04T10:15:30.123-0300', 'x': 'sem fuso 2026-11-04T10:00:00'})
    assert errs(d) == []
    assert errs(ex('wazuh-alert')) == []  # payload.timestamp com -0300 aceito


def test_g_nan_and_infinity_are_rejected():
    for const in ('NaN', 'Infinity', '-Infinity'):
        for text in ('{"severity_source": {"scheme": "x", "value": %s}}' % const,
                     '{"payload": {"a": %s}}' % const):
            try:
                c.load(text)
                raise AssertionError(f'deveria rejeitar {const}')
            except ValueError:
                pass
    # documento completo com NaN no value nao chega a ser aceito
    text = json.dumps(ex('wazuh-alert')).replace('"value": 12', '"value": NaN')
    assert 'NaN' in text
    try:
        c.load(text)
        raise AssertionError('deveria rejeitar')
    except ValueError:
        pass

def test_f_links_optional():
    for n in ('cloud-event', 'wazuh-pending-tenant'):
        d = ex(n)
        assert 'links' not in d and errs(d) == [], n
    d = ex('wazuh-alert')
    del d['links']
    assert errs(d) == []
    d = ex('wazuh-alert')
    d['links'] = {}
    assert errs(d) == []
    d['links'] = {'service': 's'}
    assert errs(d) == []


def test_envelope_misc():
    for k in ('schema_version', 'source_id', 'signal_type', 'occurred_at', 'collected_at',
              'received_at', 'severity_source', 'payload'):
        d = ex('wazuh-alert')
        del d[k]
        assert has(d, k), k
    for k in ('event_id', 'quality', 'links', 'extensions'):  # opcionais
        d = ex('wazuh-alert')
        d.pop(k, None)
        assert errs(d) == [], k
    d = ex('wazuh-alert')
    d['signal_type'] = 'wazuh'
    assert has(d, 'signal_type')
    d = ex('wazuh-alert')
    d['source_id'] = '-x'
    assert has(d, 'source_id')
    d = ex('wazuh-alert')
    d['quality'] = 'good'
    assert has(d, 'quality')
    d = ex('wazuh-alert')
    d['payload'] = []
    assert has(d, 'payload')
    # severidade: null, texto e fora de escala nao descartam o sinal
    for v in (None, 'High', 99, -1, 'abc'):
        d = ex('wazuh-alert')
        d['severity_source']['value'] = v
        assert errs(d) == [], v
    d = ex('wazuh-alert')
    d['severity_source'] = {'scheme': 'wazuh.level'}  # value ausente: aceito (regra 7 da politica SOC)
    assert errs(d) == []
    d['severity_source'] = {'value': 5}  # scheme obrigatorio
    assert has(d, 'scheme')
    d['severity_source'] = {'scheme': 'x', 'value': True}
    assert has(d, 'value')

def test_enums_are_closed_in_v1():
    # minor nao amplia enums: quality 'stale' ou algorithm 'sha512' num documento 1.1 e rejeitado por um v1.0
    d = ex('wazuh-alert')
    d.update(schema_version='1.1', quality='stale')
    assert has(d, 'quality')
    d = ex('ot-batch')
    d['schema_version'] = '1.1'
    d['batch']['integrity']['algorithm'] = 'sha512'
    assert has(d, 'algorithm')


if __name__ == '__main__':
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith('test_') and callable(f)]
    for n, f in tests:
        f()
        print('ok', n)
    print(f'{len(tests)} testes ok')
