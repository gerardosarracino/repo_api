# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
import requests
from odoo.exceptions import UserError
from odoo.tools import config


class UhuuApiTestResult(models.Model):
    _name = 'uhuu.api.test.result'
    _description = 'Resultado de prueba de endpoint Uhuu'
    _order = 'create_date desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    endpoint_id = fields.Many2one('uhuu.api.endpoint', required=True)
    environment_id = fields.Many2one('uhuu.api.environment', required=True)
    partner_id = fields.Many2one(
        'res.partner', string='Cliente asociado',
        help="Cliente asociado a este resultado de prueba, si aplica",
        tracking=True)
    status_code = fields.Integer()
    success = fields.Boolean()
    response = fields.Text()
    comentario_ia = fields.Text(string="Comentario IA")
    tested_at = fields.Datetime(default=fields.Datetime.now)
    state = fields.Selection(
        [('test_ok', 'Test OK'),
         ('test_failed', 'Test Failed')],
        string='Estado', tracking=True)

    def accion_comentario_ia(self):
        for record in self:
            if not record.success:
                comentario = record.obtener_explicacion_ia(
                    status_code=record.status_code,
                    response_text=record.response or ""
                )
                record.comentario_ia = comentario

    def obtener_explicacion_ia(self, status_code, response_text):
        api_key = self.env['ir.config_parameter'].sudo().get_param('rs_admin_console.openai_key')
        if not api_key:
            return "No se configuró la clave API de OpenAI."

        prompt = (
            f"Estoy probando una API que se conectar a odoo version 17 comunity y obtengo un error {status_code} con este cuerpo de respuesta: "
            f"{response_text}. ¿Cuál puede ser la causa probable y cómo lo corrijo?"
        )

        try:
            res = requests.post(
                'https://api.openai.com/v1/chat/completions',
                headers={
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json'
                },
                json={
                    "model": "gpt-3.5-turbo",
                    "messages": [
                        {"role": "user", "content": prompt}
                    ]
                },
                timeout=20
            )
            result = res.json()
            return result.get("choices", [{}])[0].get("message", {}).get("content", "Sin respuesta de IA")
        except Exception as e:
            return f"Error al consultar OpenAI: {str(e)}"

    # @api.model
    # def create(self, vals):
    #     endpoint = self.env['uhuu.api.endpoint'].browse(vals.get('endpoint_id'))
    #     if endpoint:
    #         # Copia partner según si es login o no
    #         if endpoint.type_login:
    #             vals['partner_id'] = endpoint.partner_id.id
    #         elif endpoint.endpoint_id_padre:
    #             vals['partner_id'] = endpoint.endpoint_id_padre.partner_id.id
    #
    #         # Copia el estado del endpoint al resultado
    #         vals['state'] = endpoint.state or 'test_failed'
    #
    #     return super(UhuuApiTestResult, self).create(vals)
