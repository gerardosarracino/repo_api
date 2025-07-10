from odoo import models, fields

class UhuuGithubCommitLog(models.Model):
    _name = 'uhuu.github.commit.log'
    _description = 'Historial de commits GitHub que dispararon pruebas'

    commit_id = fields.Char()
    message = fields.Text()
    triggered_at = fields.Datetime(default=fields.Datetime.now)
