# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
import json
import requests
import logging
import time  # Para calcular duración si se desea

_logger = logging.getLogger(__name__)

class UhuuApiEndpoint(models.Model):
    _name = 'uhuu.api.endpoint'
    _description = 'Endpoint Uhuu para pruebas automáticas'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(required=True)
    method = fields.Selection(
        [('GET', 'GET'), ('POST', 'POST'), ('PUT', 'PUT'), ('DELETE', 'DELETE')],
        required=True
    )
    route = fields.Char(required=True, tracking=True)
    body_json = fields.Text(string='Body JSON', tracking=True,
                            help="Formato JSON. Se usará como cuerpo en métodos POST/PUT.")
    headers = fields.Text(string='Cabeceras JSON', tracking=True,
                          help='Cabeceras HTTP en formato JSON. Puedes incluir Authorization.')
    query_params = fields.Text(string="Parámetros GET/DELETE JSON", tracking=True,
                               help='Diccionario de parámetros URL (solo para GET y DELETE).')
    active = fields.Boolean(default=True, tracking=True)
    endpoint_id_padre = fields.Many2one(
        'uhuu.api.endpoint', string='Endpoint de login', tracking=True)
    test_result_ids = fields.One2many(
        'uhuu.api.test.result', 'endpoint_id',
        string='Resultados de prueba', tracking=True)
    type_login = fields.Boolean(string="¿Es login?", tracking=True)
    partner_id = fields.Many2one(
        'res.partner', string='Cliente asociado',
        help="Cliente asociado a este endpoint, si aplica", tracking=True)
    response = fields.Text()
    state = fields.Selection(
        [('draft', 'Borrador'),
         ('test_ok', 'Test OK'),
         ('test_failed', 'Test Failed')],
        default='draft', string='Estado', tracking=True)
    date_last_test = fields.Datetime(string='Última Ejecución',
                                     help="Fecha del último test realizado en este endpoint", tracking=True)
    sequence = fields.Integer(
        string='Secuencia',
        help="Secuencia para ordenar los endpoints en las pruebas automáticas",
        default=10, tracking=True)

    def probar_endpoint(self, environment=None):
        self.ensure_one()

        if not environment:
            environment = self.env['uhuu.api.environment'].search([('default', '=', True)], limit=1)
            if not environment:
                raise ValueError("No hay entorno por defecto definido.")

        # Autenticación previa si existe endpoint padre
        token = None
        if self.endpoint_id_padre:
            response_login = self.endpoint_id_padre._ejecutar_llamada(environment)
            try:
                data = json.loads(response_login.get('response', '{}'))
                token = data.get('access_token') or data.get('token')
                if not token:
                    raise ValueError("No se pudo obtener token del login asignado.")
            except Exception as e:
                _logger.warning("⚠️ No se pudo extraer token del login: %s", e)

        # Ejecutar este endpoint con el token si se obtuvo
        resultado = self._ejecutar_llamada(environment, token)

        # Determinar partner de forma segura
        partner = self.partner_id or self.endpoint_id_padre.partner_id if self.endpoint_id_padre else None

        # Registrar resultado
        self.env['uhuu.api.test.result'].create({
            'endpoint_id': self.id,
            'environment_id': environment.id,
            'partner_id': partner.id if partner else False,
            'status_code': resultado.get('status_code'),
            'success': resultado.get('success'),
            'response': resultado.get('response'),
            'state': 'test_ok' if resultado.get('success') else 'test_failed',
            # Agrega aquí 'duration': resultado.get('duration') si usas tiempo
        })

        # Actualiza estado y respuesta en el endpoint
        self.response = resultado.get('response')
        self.state = 'test_ok' if resultado.get('success') else 'test_failed'
        self.date_last_test = fields.Datetime.now()

        return resultado.get('success')

    def _ejecutar_llamada(self, environment, token=None):
        url = environment.base_url.rstrip('/') + '/' + self.route.lstrip('/')
        method = self.method.upper()

        # Headers
        try:
            headers = json.loads(self.headers or "{}")
        except Exception as e:
            headers = {}
            _logger.warning("⚠️ Error al interpretar headers JSON: %s", e)

        if token:
            headers['Authorization'] = f"Bearer {token}"
        elif environment.token:
            headers['Authorization'] = f"Bearer {environment.token}"

        # Body
        try:
            body = json.loads(self.body_json or "{}")
        except Exception as e:
            body = {}
            _logger.warning("⚠️ Error al interpretar body JSON: %s", e)

        # Query Params
        try:
            query_params = json.loads(self.query_params or "{}")
        except Exception as e:
            query_params = {}
            _logger.warning("⚠️ Error al interpretar query_params JSON: %s", e)

        # Validación preventiva para 'fields'
        fields_list = query_params.get('fields', [])
        if isinstance(fields_list, list):
            for f in fields_list:
                if isinstance(f, list):
                    _logger.warning("⚠️ 'fields' contiene una lista anidada. Corrígelo para evitar errores 500.")
                    query_params['fields'] = f
                    break

        # Logs debug
        _logger.warning("📤 Método: %s", method)
        _logger.warning("📤 URL: %s", url)
        _logger.warning("📤 Headers: %s", headers)
        _logger.warning("📦 Body: %s", body)
        _logger.warning("🔎 Query Params: %s", query_params)

        try:
            start = time.time()
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                json=body if method in ['POST', 'PUT'] else None,
                params={k: json.dumps(v) for k, v in query_params.items()} if method in ['GET', 'DELETE'] else None,
                timeout=15
            )
            duration = time.time() - start
            return {
                'status_code': response.status_code,
                'success': response.status_code < 400,
                'response': response.text,
                'duration': duration,
            }
        except Exception as e:
            _logger.error("❌ Error al ejecutar llamada: %s", e)
            return {
                'status_code': 0,
                'success': False,
                'response': f"{type(e).__name__}: {str(e)}"
            }

    def ejecutar_pruebas_masivas(self):
        endpoints = self.search([('active', '=', True)])
        entorno_default = self.env['uhuu.api.environment'].search([('default', '=', True)], limit=1)
        for endpoint in endpoints:
            try:
                endpoint.probar_endpoint(environment=entorno_default)
            except Exception as e:
                _logger.error("❌ Error en prueba masiva para %s: %s", endpoint.name, e)
                self.env['uhuu.api.test.result'].create({
                    'endpoint_id': endpoint.id,
                    'environment_id': entorno_default.id if entorno_default else False,
                    'status_code': 0,
                    'success': False,
                    'response': f"{type(e).__name__}: {str(e)}",
                })
