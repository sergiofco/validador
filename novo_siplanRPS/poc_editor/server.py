"""
Servidor local para o editor analise_siplan_fluxo.
Autentica via InteractiveBrowserCredential (Azure CLI app — sem App Registration proprio).
Acessa o warehouse diretamente via pyodbc + token AD.

Uso:
    cd poc_editor
    python server.py
Acesse: http://localhost:8080
"""
import base64
import json
import struct
import threading
import webbrowser
from datetime import date, datetime, timedelta

import pyodbc
import requests
from azure.identity import InteractiveBrowserCredential
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

# ── Configuracao ──────────────────────────────────────────────────────────────
SQL_ENDPOINT  = (
    'beu5bmmdbuwedpv62ucm524jzi-j5uifqqkrzyuxjcrxjckqzjkmm'
    '.datawarehouse.fabric.microsoft.com'
)
ODBC_DRIVER   = 'ODBC Driver 18 for SQL Server'
TABLE         = 'wh_siplan_fluxo.dbo.analise_siplan_fluxo'

# Usado apenas para triggar notebook (fallback nao necessario por ora)
WORKSPACE_ID  = 'c282684f-8e0a-4b71-a451-ba44a8652a63'
NOTEBOOK_ID   = 'a0ea5f23-6b21-4fe8-a6d4-18da16d14410'

PORT = 8080

# ── Auth ──────────────────────────────────────────────────────────────────────
_cred = None
_cred_lock = threading.Lock()


def get_cred() -> InteractiveBrowserCredential:
    global _cred
    with _cred_lock:
        if _cred is None:
            _cred = InteractiveBrowserCredential()
    return _cred


def get_db_token() -> str:
    return get_cred().get_token('https://database.windows.net/.default').token


def decode_upn(token: str) -> str:
    try:
        payload = token.split('.')[1]
        payload += '=' * (-len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload))
        return claims.get('upn') or claims.get('preferred_username') or claims.get('email') or ''
    except Exception:
        return ''


# ── Banco ─────────────────────────────────────────────────────────────────────
def get_conn():
    token = get_db_token()
    tb = token.encode('utf-16-le')
    ts = struct.pack(f'<I{len(tb)}s', len(tb), tb)
    return pyodbc.connect(
        f'DRIVER={{{ODBC_DRIVER}}};SERVER={SQL_ENDPOINT};Encrypt=Yes;TrustServerCertificate=No;',
        attrs_before={1256: ts},
        autocommit=False,
    )


class _JSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super().default(obj)


def rows_to_json(cursor):
    cols = [col[0] for col in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


# ── Flask ─────────────────────────────────────────────────────────────────────
app = Flask(__name__, static_folder='.')
app.json_encoder = _JSONEncoder
CORS(app)


@app.route('/')
def index():
    return send_from_directory('.', 'analise_siplan_editor.html')


@app.route('/msal-browser.min.js')
def msal_js():
    return send_from_directory('.', 'msal-browser.min.js')


@app.route('/api/whoami')
def whoami():
    try:
        email = decode_upn(get_db_token())
        return jsonify({'email': email, 'ok': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 401


@app.route('/api/data')
def get_data():
    try:
        conn = get_conn()
        cur  = conn.cursor()
        cur.execute(f"""
            SELECT
                atividade_id,
                nome,
                unidade,
                gerencia,
                area,
                linguagem,
                mes,
                autonomia,
                CONVERT(VARCHAR(10), dataPrimeiraSessao, 120) AS dataPrimeiraSessao,
                custos_foto,
                custos_editavel,
                [Status],
                CONVERT(VARCHAR(16), data_entrega, 120)       AS data_entrega,
                quem
            FROM {TABLE}
            ORDER BY data_entrega DESC
        """)
        data = rows_to_json(cur)
        conn.close()
        # Devolve no mesmo formato que a REST API usaria
        return app.response_class(
            response=json.dumps({'results': [{'columns': [{'name': k} for k in (data[0].keys() if data else [])], 'rows': [[row[k] for k in row] for row in data]}]}, cls=_JSONEncoder),
            mimetype='application/json'
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/update', methods=['POST'])
def update_status():
    try:
        body         = request.json or {}
        atividade_id = body.get('atividade_id')
        new_status   = body.get('new_status', '')

        if not atividade_id or not new_status:
            return jsonify({'error': 'atividade_id e new_status sao obrigatorios'}), 400

        STATUSES_PERMITIDOS = {
            'Enviada', 'Reenviada', 'Em revisao', 'AutonomiaUO',
            'Aprovado', 'Nao aprovado', 'Em revisão', 'Não aprovado',
        }
        if new_status not in STATUSES_PERMITIDOS:
            return jsonify({'error': f'Status invalido: {new_status}'}), 400

        token    = get_db_token()
        usuario  = decode_upn(token) or 'interface'
        now_brt  = datetime.utcnow() - timedelta(hours=3)

        conn = get_conn()
        cur  = conn.cursor()
        cur.execute(
            f'UPDATE {TABLE}'
            ' SET [Status] = ?, [Modificado] = ?, [Modificado por] = ?'
            ' WHERE atividade_id = ?',
            (new_status, now_brt, usuario, int(atividade_id))
        )
        conn.commit()
        rows_affected = cur.rowcount
        conn.close()

        if rows_affected == 0:
            return jsonify({'error': f'atividade_id {atividade_id} nao encontrada'}), 404

        return jsonify({'ok': True, 'atividade_id': atividade_id, 'new_status': new_status})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print('Autenticando... o browser vai abrir para login.')
    try:
        tok   = get_db_token()
        email = decode_upn(tok)
        print(f'Autenticado como: {email or "(email nao disponivel no token)"}')
    except Exception as e:
        print(f'Erro de autenticacao: {e}')
        raise SystemExit(1)

    url = f'http://localhost:{PORT}'
    print(f'Servidor iniciado: {url}')
    threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    app.run(port=PORT, debug=False, use_reloader=False)
