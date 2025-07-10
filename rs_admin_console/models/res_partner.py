# -*- coding: utf-8 -*-

from odoo import models, fields


class ResPartner(models.Model):
    _inherit = 'res.partner'

    github_repo_path = fields.Char(
        string="Ruta del repositorio GitHub"
    )