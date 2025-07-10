from odoo import models, fields

class UhuuApiEnvironment(models.Model):
    _name = 'uhuu.api.environment'
    _description = 'Entorno de pruebas Uhuu'

    name = fields.Char(required=True)
    base_url = fields.Char(required=True)
    token = fields.Char()
    default = fields.Boolean(default=False)
