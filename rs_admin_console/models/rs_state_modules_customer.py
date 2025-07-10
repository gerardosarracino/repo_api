from odoo import models, fields, _
from odoo.exceptions import UserError


class RSModuleStatus(models.Model):
    _name = 'rs.module.status'
    _description = 'Estado de módulo RS'

    name = fields.Char(string='Nombre del Módulo', required=True, index=True)
    partner_id = fields.Many2one('res.partner', string='Cliente', required=True,)
    installed = fields.Boolean(string='Instalado', default=False)
    installed_version = fields.Char(string='Versión Instalada')
    repo_version = fields.Char(string='Versión en Repositorio')
    summary = fields.Text(string='Resumen')
    last_update = fields.Datetime(string='Última actualización', default=fields.Datetime.now)
    module_updated = fields.Boolean(string='Módulo actualizado', default=False)
    last_chek = fields.Datetime(string='Última verificación', default=fields.Datetime.now)

    def _get_ir_module(self):
        self.ensure_one()
        ir_module = self.env['ir.module.module'].sudo().search([('name', '=', self.name)], limit=1)
        if not ir_module:
            raise UserError(f"❌ Módulo {self.name} no se encontró en ir.module.module.")
        return ir_module

    def action_install_module(self):
        for rec in self:
            ir_module = rec._get_ir_module()
            if ir_module.state != 'installed':
                ir_module.button_immediate_install()
            else:
                raise UserError(f"⚠️ El módulo {rec.name} ya está instalado.")

    def action_upgrade_module(self):
        for rec in self:
            ir_module = rec._get_ir_module()
            if ir_module.state == 'installed':
                ir_module.button_immediate_upgrade()
            else:
                raise UserError(f"⚠️ El módulo {rec.name} no está instalado para poder actualizarse.")

    def action_uninstall_module(self):
        for rec in self:
            ir_module = rec._get_ir_module()
            if ir_module.state == 'installed':
                ir_module.button_immediate_uninstall()
            else:
                raise UserError(f"⚠️ El módulo {rec.name} no está instalado.")
