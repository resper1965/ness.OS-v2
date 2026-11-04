"""Validador consumidor do contrato de sinal v1 (consumidor v1.0).

Escrito somente a partir de docs/specs/signal-contract-v1.md, do schema e dos exemplos.
Uso: python3 signal_v1_consumer.py [--stored] sinal.json  -> "ACEITO" ou "REJEITADO: motivo" (exit 0/1).
Sem --stored valida o envelope de ENTRADA (tenant_id null ou ausente); com --stored, o registro armazenado.
"""
import hashlib
from fractions import Fraction
import json
import re
import sys
from datetime import datetime, timedelta, timezone

REQUIRED = ('schema_version', 'source_id', 'signal_type', 'occurred_at',
            'collected_at', 'received_at', 'severity_source', 'payload')  # + tenant_id no registro armazenado
INSTANT = re.compile(r'([0-9]{4})-([0-9]{2})-([0-9]{2})T([0-9]{2}):([0-9]{2}):([0-9]{2})'
                     r'(\.[0-9]+)?(Z|[+-][0-9]{2}:[0-9]{2})')
SOURCE_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,127}')
SIGNAL_TYPE = re.compile(r'[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+')
VERSION = re.compile(r'([0-9]+)\.(0|[1-9][0-9]*)')
DIGEST = re.compile(r'[0-9a-f]{64}')
EXT_KEY = re.compile(r'[a-z][a-z0-9_]*')
QUALITY = ('complete', 'partial', 'delayed')
MAX_SAFE_INT = 2 ** 53 - 1


def parse_instant(v):
    """RFC 3339 com fuso explicito (Z ou +hh:mm). Devolve os segundos desde a epoca (Fraction exata, fracao
    completa preservada, sem truncar a microssegundos) ou None."""
    if not isinstance(v, str):
        return None
    m = INSTANT.fullmatch(v)
    if not m:
        return None
    y, mo, d, h, mi, s = (int(x) for x in m.groups()[:6])
    frac, tz = m.group(7), m.group(8)
    try:
        if tz == 'Z':
            off = timezone.utc
        else:
            oh, om = int(tz[1:3]), int(tz[4:6])
            if oh > 23 or om > 59:
                return None
            off = timezone(timedelta(hours=oh, minutes=om) * (-1 if tz[0] == '-' else 1))
        whole = (datetime(y, mo, d, h, mi, s, tzinfo=off) - datetime(1970, 1, 1, tzinfo=timezone.utc)) // timedelta(seconds=1)
        return whole + (Fraction(int(frac[1:]), 10 ** (len(frac) - 1)) if frac else Fraction(0))
    except ValueError:  # data/hora impossivel (inclui segundo 60)
        return None


_ESC = {'"': '\\"', '\\': '\\\\', '\b': '\\b', '\f': '\\f', '\n': '\\n', '\r': '\\r', '\t': '\\t'}


def jcs(v):
    """Forma canonica RFC 8785. Suporta objeto, lista, texto, inteiro seguro, bool e null.
    ponytail: sem float (serializacao ES6) nem inteiro > 2^53-1; upgrade: portar o algoritmo do RFC 8785 §3.2.2.3."""
    if v is None:
        return 'null'
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, int):
        if abs(v) > MAX_SAFE_INT:
            raise ValueError('inteiro fora da faixa segura do JCS')
        return str(v)
    if isinstance(v, str):
        return '"' + ''.join(_ESC.get(c) or (f'\\u{ord(c):04x}' if ord(c) < 0x20 else c) for c in v) + '"'
    if isinstance(v, list):
        return '[' + ','.join(jcs(x) for x in v) + ']'
    if isinstance(v, dict):
        # ordem por unidades de codigo UTF-16, nao por code point
        items = sorted(v.items(), key=lambda kv: kv[0].encode('utf-16-be', 'surrogatepass'))
        return '{' + ','.join(jcs(k) + ':' + jcs(x) for k, x in items) + '}'
    raise ValueError(f'tipo nao suportado no JCS: {type(v).__name__}')


def payload_digest(payload):
    return hashlib.sha256(jcs(payload).encode('utf-8')).hexdigest()


def _nonempty_str(v):
    return isinstance(v, str) and v != ''


def doc_id(doc):
    return f"source_id={doc.get('source_id')!r} event_id={doc.get('event_id')!r}"

def validate(doc, stored=False):
    """(erros, avisos). Sem erros = aceitar. Campos desconhecidos sao ignorados.
    stored=False: envelope de entrada (tenant_id null/ausente; preenchido = rejeitado).
    stored=True: registro armazenado (tenant_id obrigatorio, texto ou null)."""
    errs, warns = [], []
    if not isinstance(doc, dict):
        return ['documento nao e objeto'], warns
    missing = [k for k in REQUIRED + (('tenant_id',) if stored else ()) if k not in doc]
    if missing:
        errs.append('campo obrigatorio ausente: ' + ', '.join(missing))

    ver = doc.get('schema_version')
    if 'schema_version' in doc:
        m = VERSION.fullmatch(ver) if isinstance(ver, str) else None
        if m and m.group(1) != '1':
            errs.append(f'major incompativel: {ver} (suportado: 1.N)')
        elif not m or m.group(1) != '1':
            errs.append(f'schema_version invalido: {ver!r}')

    if 'source_id' in doc and not (isinstance(doc['source_id'], str) and SOURCE_ID.fullmatch(doc['source_id'])):
        errs.append('source_id invalido')
    if 'tenant_id' in doc and doc['tenant_id'] is not None:
        if not stored:
            errs.append(f"tenant_id preenchido na entrada: campo=tenant_id valor={doc['tenant_id']!r} {doc_id(doc)}")
        elif not _nonempty_str(doc['tenant_id']):
            errs.append('tenant_id deve ser texto nao vazio ou null')
    st = doc.get('signal_type')
    if 'signal_type' in doc and not (isinstance(st, str) and SIGNAL_TYPE.fullmatch(st)):
        errs.append('signal_type invalido')
    if 'event_id' in doc and not _nonempty_str(doc['event_id']):
        errs.append('event_id deve ser texto nao vazio')

    inst = {}
    for k in ('occurred_at', 'collected_at', 'received_at'):
        if k in doc:
            inst[k] = parse_instant(doc[k])
            if inst[k] is None:
                errs.append(f'{k} invalido (RFC 3339 com fuso Z ou +hh:mm): {doc[k]!r}')
    if len(inst) == 3 and None not in inst.values():
        if not inst['occurred_at'] <= inst['collected_at'] <= inst['received_at']:
            warns.append('ordem occurred_at <= collected_at <= received_at violada (aceito)')

    if 'severity_source' in doc:
        s = doc['severity_source']
        if not isinstance(s, dict):
            errs.append('severity_source deve ser objeto')
        else:
            if not _nonempty_str(s.get('scheme')):
                errs.append('severity_source.scheme obrigatorio')
            # value ausente ou null: aceito (nao descarta; politica de atendimento, regra 7)
            if s.get('value') is not None and (isinstance(s['value'], bool)
                                             or not isinstance(s['value'], (int, float, str))):
                errs.append('severity_source.value deve ser numero, texto ou null')
    if 'payload' in doc and not isinstance(doc['payload'], dict):
        errs.append('payload deve ser objeto')
    if 'quality' in doc and doc['quality'] not in QUALITY:
        errs.append('quality invalido')

    if 'links' in doc:
        ln = doc['links']
        if not isinstance(ln, dict):
            errs.append('links deve ser objeto')
        else:
            for k in ('asset', 'service', 'cluster'):
                if k in ln and not _nonempty_str(ln[k]):
                    errs.append(f'links.{k} deve ser texto nao vazio')

    if 'extensions' in doc:
        ex = doc['extensions']
        if not isinstance(ex, dict):
            errs.append('extensions deve ser objeto')
        else:
            for k, v in ex.items():
                if not EXT_KEY.fullmatch(k) or not isinstance(v, dict):
                    errs.append(f'extensions.{k} invalido (chave de origem -> objeto)')

    if st == 'ot.batch':
        if 'batch' not in doc:
            errs.append('batch obrigatorio em ot.batch')
        else:
            errs += _batch(doc['batch'], doc.get('payload'), inst, warns)
    elif 'batch' in doc:
        errs.append(f'batch proibido em {st}')
    return errs, warns


def _batch(b, payload, inst, warns):
    if not isinstance(b, dict):
        return ['batch deve ser objeto']
    errs = []
    for k in ('batch_id', 'rules_version'):
        if not _nonempty_str(b.get(k)):
            errs.append(f'batch.{k} obrigatorio')
    iv = b.get('interval')
    start = end = None
    if not isinstance(iv, dict) or 'start' not in iv or 'end' not in iv:
        errs.append('batch.interval {start,end} obrigatorio')
    else:
        start, end = parse_instant(iv['start']), parse_instant(iv['end'])
        if start is None or end is None:
            errs.append('batch.interval com instante invalido (RFC 3339 com fuso)')
        elif not start < end:
            errs.append('batch.interval: start deve ser < end')
        else:
            if inst.get('occurred_at') and inst['occurred_at'] != start:
                warns.append('occurred_at do lote difere de interval.start (aceito)')
            if inst.get('collected_at') and inst['collected_at'] != end:
                warns.append('collected_at do lote difere de interval.end (aceito)')
    ig = b.get('integrity')
    if isinstance(payload, dict):  # o digest so cobre inteiros seguros e strings: o resto e rejeitado
        try:
            digest = payload_digest(payload)
        except (ValueError, UnicodeEncodeError) as e:
            digest = None
            errs.append(f'payload fora do subconjunto JCS (float, inteiro > 2^53-1, surrogate isolado): {e}')
    if not isinstance(ig, dict):
        errs.append('batch.integrity obrigatorio')
        return errs
    if ig.get('algorithm') != 'sha256':
        errs.append('batch.integrity.algorithm deve ser sha256')
    if not (isinstance(ig.get('digest'), str) and DIGEST.fullmatch(ig['digest'])):
        errs.append('batch.integrity.digest deve ser sha256 hex minusculo')
    elif isinstance(payload, dict) and digest is not None and digest != ig['digest']:
        errs.append('batch.integrity.digest nao confere com o JCS do payload')
    ec = ig.get('event_count')
    if 'event_count' in ig and (isinstance(ec, bool) or not isinstance(ec, int) or ec < 0):
        errs.append('batch.integrity.event_count deve ser inteiro >= 0')
    return errs


def ingest(doc, resolve_tenant, received_at):
    """Recepcao no Hub: documento de ENTRADA (tenant_id preenchido e rejeitado); o Hub grava
    tenant_id (resolvido) e received_at. resolve_tenant(source_id) -> tenant ou None (sem vinculo
    ou vinculos conflitantes). Devolve o registro armazenado ou levanta ValueError."""
    errs, warns = validate(doc)
    if errs:
        raise ValueError('; '.join(errs))
    known = {k: v for k, v in doc.items() if k in REQUIRED + ('event_id', 'quality', 'links', 'batch', 'extensions')}
    known['tenant_id'] = resolve_tenant(doc['source_id'])
    known['received_at'] = received_at
    return {'record': known, 'pending_tenant_review': known['tenant_id'] is None,
            'ignored': sorted(set(doc) - set(known)), 'warnings': warns}

def idempotency_key(doc):
    """(source_id, event_id); lote: (source_id, batch_id). Sem tenant_id. None = sem deduplicacao."""
    if doc.get('signal_type') == 'ot.batch':
        return (doc['source_id'], doc['batch']['batch_id'])
    return (doc['source_id'], doc['event_id']) if doc.get('event_id') else None

def clock_skew(record):
    """received_at - collected_at em segundos (Fraction), derivado do registro (sem campo novo)."""
    return parse_instant(record['received_at']) - parse_instant(record['collected_at'])

class Store:
    """Registro por chave de idempotencia. put -> 'new' | 'duplicate' | 'conflict'.
    Mesma chave + mesmo payload = duplicate (devolve o salvo); payload diferente = conflict registrado, nao sobrescreve."""
    def __init__(self):
        self.records, self.conflicts = {}, []

    def put(self, record):
        key = idempotency_key(record)
        if key is None:
            return 'new'
        old = self.records.get(key)
        if old is None:
            self.records[key] = record
            return 'new'
        if json.dumps(old['payload'], sort_keys=True) == json.dumps(record['payload'], sort_keys=True):
            return 'duplicate'
        self.conflicts.append((key, record))
        return 'conflict'

def _no_dup(pairs):
    d = {}
    for k, v in pairs:
        if k in d:
            raise ValueError(f'chave duplicada no JSON: {k}')
        d[k] = v
    return d


def _no_const(name):
    raise ValueError(f'constante JSON invalida: {name}')

def load(text):
    return json.loads(text, object_pairs_hook=_no_dup, parse_constant=_no_const)


if __name__ == '__main__':
    stored = '--stored' in sys.argv
    try:
        errs, _ = validate(load(open(sys.argv[-1], encoding='utf-8').read()), stored=stored)
    except ValueError as e:
        errs = [f'JSON invalido: {e}']
    print('ACEITO' if not errs else 'REJEITADO: ' + '; '.join(errs))
    sys.exit(1 if errs else 0)
