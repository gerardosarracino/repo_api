# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from datetime import datetime
import json
from odoo.exceptions import UserError
import requests
import base64

import logging

_logger = logging.getLogger(__name__)


class ClientConsola(models.Model):
    _name = 'client.consola'
    _description = 'Consola de Cliente - Uhuu y GitHub'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Nombre', tracking=True,)
    partner_id = fields.Many2one(
        'res.partner', string='Cliente', required=True, tracking=True,)

    date_last_check_api = fields.Datetime(string='Último check API')
    status_last_check_api = fields.Selection([
        ('pending', 'Pendiente'),
        ('success', 'Test OK'),
        ('failed', 'Test Failed'),
    ], string='Estatus Último Check APIs')
    percentage_passed_api = fields.Float(string='Porcentaje Passed API')

    # Placeholder para futuras integraciones con GitHub
    date_last_check_github = fields.Datetime(string='Último check GitHub')
    status_last_check_github = fields.Char(string='Estatus Último Check GitHub')
    percentage_passed_github = fields.Float(string='Porcentaje Passed GitHub')
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('running', 'Ejecutando'),
        ('success', 'Éxito'),
        ('failed', 'Fallido'),
    ], string='Estado general', default='draft', tracking=True)
    test_result_count = fields.Integer(
        string='Resultados de Pruebas',
        compute='_compute_test_result_count',
        store=False,
    )
    count_modules_installed = fields.Integer(
        string='Módulos Instalados',
        compute='_compute_count_modules_installed',
        store=False,
    )
    sha_master = fields.Char(string='Último SHA del Repositorio Maestro', tracking=True)
    fecha_sha_master = fields.Datetime(string='Fecha Último SHA', tracking=True)
    sha_remoto = fields.Char(string='Último SHA Cliente', tracking=True)
    actualizado = fields.Boolean(string='¿Actualizado?', compute='_compute_actualizado', store=True)

    @api.depends('partner_id')
    def _compute_count_modules_installed(self):
        for record in self:
            record.count_modules_installed = self.env['rs.module.status'].search_count([
                ('partner_id', '=', record.partner_id.id),
                ('installed', '=', True)
            ])

    @api.model
    def cron_ejecutar_pruebas_todos_los_clientes(self):
        clientes = self.search([])
        for cliente in clientes:
            try:
                cliente.action_ejecutar_pruebas_api()
            except Exception as e:
                cliente.message_post(body=f"❌ Error al ejecutar pruebas automáticas: {str(e)}")

    def _compute_test_result_count(self):
        for record in self:
            record.test_result_count = self.env['uhuu.api.test.result'].search_count([
                ('partner_id', '=', record.partner_id.id)
            ])

    def action_ver_resultados_test(self):
        self.ensure_one()
        return {
            'name': _('Resultados de Pruebas'),
            'type': 'ir.actions.act_window',
            'res_model': 'uhuu.api.test.result',
            'view_mode': 'tree,form',
            'domain': [('partner_id', '=', self.partner_id.id)],
            'context': dict(self.env.context),
        }

    def action_ver_modulos_instalados(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Módulos del Repositorio',
            'res_model': 'rs.module.status',
            'view_mode': 'tree,form',
            'domain': [('partner_id', '=', self.partner_id.id)],
            'context': {
                'group_by': 'installed',
            },
            'order': 'installed desc',
        }

    def action_ejecutar_pruebas_api(self):
        for record in self:
            # Cambiar estado y forzar commit para que el estado se vea en UI
            record.state = 'running'
            record._cr.commit()

            # 1. Buscar endpoint de login para el cliente actual
            endpoint_login = self.env['uhuu.api.endpoint'].search([
                ('partner_id', '=', record.partner_id.id),
                ('type_login', '=', True),
                ('active', '=', True),
            ], limit=1)

            if not endpoint_login:
                raise UserError("No se encontró un endpoint de login para este cliente.")

            # 2. Buscar entorno por defecto
            environment = self.env['uhuu.api.environment'].search([('default', '=', True)], limit=1)
            if not environment:
                raise UserError("No se encontró un entorno por defecto.")

            # 3. Ejecutar login
            token = None
            response_login = endpoint_login._ejecutar_llamada(environment)

            # Crear registro de resultado del login (exitoso o no)
            success_login = response_login.get('success', False)
            self.env['uhuu.api.test.result'].create({
                'endpoint_id': endpoint_login.id,
                'environment_id': environment.id,
                'status_code': response_login.get('status_code'),
                'success': success_login,
                'response': response_login.get('response'),
                'partner_id': record.partner_id.id,
                'state': 'test_ok' if success_login else 'test_failed',
            })

            # 4. Validar token y terminar si falló
            try:
                data = json.loads(response_login.get('response', '{}'))
                token = data.get('access_token') or data.get('token')
                if not token:
                    raise ValueError("No se pudo obtener token del login.")
            except Exception as e:
                # Si falla el login o el parseo del token, se detiene todo
                record.state = 'failed'
                record.status_last_check_api = 'failed'
                record.percentage_passed_api = 0
                record.date_last_check_api = fields.Datetime.now()
                record.message_post(body=f"❌ Error durante login: {str(e)}")
                return

            # 5. Ejecutar pruebas para endpoints activos que no son login
            endpoints = self.env['uhuu.api.endpoint'].search([
                ('type_login', '=', False),
                ('active', '=', True)
            ])
            total = len(endpoints)
            passed = 0
            failed_names = []

            for ep in endpoints:
                resultado = ep._ejecutar_llamada(environment, token=token)
                self.env['uhuu.api.test.result'].create({
                    'endpoint_id': ep.id,
                    'environment_id': environment.id,
                    'status_code': resultado.get('status_code'),
                    'success': resultado.get('success'),
                    'response': resultado.get('response'),
                    'partner_id': record.partner_id.id,
                    'state': 'test_ok' if resultado.get('success') else 'test_failed',
                })

                if resultado.get('success'):
                    passed += 1
                else:
                    failed_names.append(ep.name)

            # 6. Actualizar métricas y estado del test
            record.date_last_check_api = fields.Datetime.now()
            record.status_last_check_api = 'success' if passed == total else 'failed'
            record.percentage_passed_api = (passed / total * 100) if total else 0
            record.state = 'success' if passed == total else 'failed'

            # 7. Reporte en el chatter
            msg = f"🧪 Pruebas ejecutadas para el cliente **{record.partner_id.name}** usando token de login.\n\n"
            msg += f"✅ Endpoints exitosos: {passed}/{total}\n"
            if failed_names:
                msg += "❌ Fallaron los siguientes endpoints:\n<ul>"
                for name in failed_names:
                    msg += f"<li>{name}</li>"
                msg += "</ul>"
            record.message_post(body=msg)

    def action_consultar_shas(self):
        self.action_consultar_sha_master()
        self.action_consultar_sha_remoto()
        self.date_last_check_github = fields.Datetime.now()

    @api.depends('sha_master', 'sha_remoto')
    def _compute_actualizado(self):
        for rec in self:
            rec.actualizado = bool(rec.sha_master and rec.sha_remoto and rec.sha_master == rec.sha_remoto)

    def action_consultar_sha_master(self):
        config = self.env['ir.config_parameter'].sudo()
        token = config.get_param("client_consola.github_token")
        repo = config.get_param("client_consola.github_repo")
        branch = config.get_param("client_consola.github_branch")

        if not all([token, repo, branch]):
            raise UserError("Faltan datos en la configuración de GitHub (token, repo o rama).")

        url = f"https://api.github.com/repos/{repo}/commits/{branch}"
        headers = {'Authorization': f'token {token}'}

        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                sha = data.get("sha")
                for record in self:
                    record.write({
                        'sha_master': sha,
                        'fecha_sha_master': fields.Datetime.now(),
                    })
                    record.message_post(body=f"🔄 SHA maestro actualizado: <b>{sha}</b>")
            else:
                raise UserError(f"Error al consultar GitHub: {response.status_code} - {response.text}")
        except Exception as e:
            raise UserError(f"Excepción al consultar GitHub: {str(e)}")

    def _actualizar_sha_en_clientes(self, sha):
        clientes = self.env['client.consola'].search([])
        for cliente in clientes:
            cliente.write({
                'sha_master': sha,
                'fecha_sha_master': fields.Datetime.now()
            })
            cliente.message_post(body=f"🔄 SHA maestro actualizado desde GitHub: <code>{sha}</code>")

    def action_consultar_sha_remoto(self):
        for rec in self:
            if not rec.partner_id or not rec.partner_id.website:
                raise UserError("Este cliente no tiene URL definida en el campo 'Sitio web'.")

            if not rec.partner_id.github_repo_path:
                raise UserError(
                    "Este cliente no tiene definida la ruta del repositorio GitHub (campo github_repo_path).")

            url = rec.partner_id.website.rstrip('/') + '/uhuu/github/sha'
            token = "token-brokerlink-rs-123456"  # 🔐 tu token fijo

            payload = {
                "accion": "sha",
                "repo_path": rec.partner_id.github_repo_path
            }
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            _logger.info(f"🔁 Enviando solicitud SHA remoto a {url}")
            _logger.info(f"📦 Payload: {json.dumps(payload)}")
            _logger.info(f"🔐 Headers: {headers}")

            try:
                response = requests.post(
                    url,
                    headers={"Authorization": f"Bearer {token}"},
                    json={
                        "accion": "sha",
                        "repo_path": rec.partner_id.github_repo_path
                    },
                    timeout=15
                )

                # Agrega este log aquí:
                _logger.info(f"📨 Respuesta recibida del cliente: {response.status_code} - {response.text}")

                if response.status_code == 200:
                    data = response.json()
                    sha = data.get("result", {}).get("sha")
                    if not sha:
                        raise UserError("La respuesta no contiene SHA válido.")

                    rec.sha_remoto = sha
                    rec.message_post(body=f"🔄 SHA remoto actualizado desde cliente: <code>{sha}</code>")
                else:
                    raise UserError(f"Error {response.status_code}: {response.text}")
            except Exception as e:
                raise UserError(f"No se pudo conectar con el cliente: {str(e)}")

    def action_actualizar_modulos_repo(self):
        for rec in self:
            config = self.env['res.config.settings'].get_github_settings()

            token = config['token']
            repo = config['repo']
            branch = config['branch']

            if not token or not repo or not branch:
                raise UserError("❌ Faltan parámetros: token, repo o branch.")

            headers = {
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github+json"
            }

            api_base = f"https://api.github.com/repos/{repo}/contents"
            response = requests.get(f"{api_base}?ref={branch}", headers=headers)

            if response.status_code != 200:
                raise UserError(f"Error {response.status_code} al listar carpetas: {response.text}")

            contenido = response.json()
            carpetas = [item for item in contenido if item['type'] == 'dir']

            ModelStatus = self.env['rs.module.status']
            nuevos, actualizados, errores = 0, 0, 0

            for carpeta in carpetas:
                nombre_directorio = carpeta['name']
                manifest_url = f"{api_base}/{nombre_directorio}/__manifest__.py?ref={branch}"

                manifest_resp = requests.get(manifest_url, headers=headers)
                if manifest_resp.status_code != 200:
                    errores += 1
                    continue  # No es un módulo válido o no tiene manifest

                try:
                    content_base64 = manifest_resp.json().get("content")
                    content_decoded = base64.b64decode(content_base64)
                    manifest_dict = eval(content_decoded, {"__builtins__": {}})

                    version = manifest_dict.get('version', 'desconocida')
                    summary = manifest_dict.get('summary', 'Sin resumen')

                    # usamos el nombre del directorio como clave (no el 'name' del manifest)
                    status = ModelStatus.search([
                        ('name', '=', nombre_directorio),
                        ('partner_id', '=', rec.partner_id.id)
                    ], limit=1)

                    if not status:
                        ModelStatus.create({
                            'name': nombre_directorio,
                            'partner_id': rec.partner_id.id,
                            'repo_version': version,
                            'summary': summary,
                            'last_update': fields.Datetime.now()
                        })
                        nuevos += 1
                    else:
                        status.repo_version = version
                        status.summary = summary
                        status.last_update = fields.Datetime.now()
                        actualizados += 1

                except Exception as e:
                    errores += 1
                    _logger.warning(f"⚠️ Error al procesar módulo {nombre_directorio}: {e}")
                    continue

            rec.message_post(body=_(
                f"✅ Módulos obtenidos desde GitHub.<br/>"
                f"📦 Nuevos: {nuevos}<br/>"
                f"♻️ Actualizados: {actualizados}<br/>"
                f"❌ Errores: {errores}"
            ))

    def action_verificar_estado_modulos_odoo(self):
        IrModule = self.env['ir.module.module'].sudo()

        for rec in self:
            if not rec.partner_id:
                raise UserError("El cliente no tiene partner_id asignado.")

            modules = self.env['rs.module.status'].search([
                ('partner_id', '=', rec.partner_id.id)
            ])

            encontrados, no_encontrados, actualizados, desactualizados = 0, 0, 0, 0

            for mod in modules:
                mod.last_chek = fields.Datetime.now()
                ir_mod = IrModule.search([('name', '=', mod.name)], limit=1)

                if ir_mod and ir_mod.state == 'installed':
                    mod.installed = True
                    mod.installed_version = ir_mod.installed_version or 'desconocida'
                    encontrados += 1

                    if mod.repo_version and mod.installed_version:
                        if mod.repo_version == mod.installed_version:
                            mod.module_updated = True
                            actualizados += 1
                        else:
                            mod.module_updated = False
                            desactualizados += 1
                    else:
                        mod.module_updated = False
                else:
                    mod.installed = False
                    mod.installed_version = None
                    mod.module_updated = False
                    no_encontrados += 1

            rec.message_post(body=(
                f"🔍 Verificación completada para <b>{rec.partner_id.name}</b>:<br/>"
                f"✔️ Instalados: {encontrados}<br/>"
                f"🆕 No instalados: {no_encontrados}<br/>"
                f"🔄 Actualizados: {actualizados}<br/>"
                f"⚠️ Desactualizados: {desactualizados}"
            ))

