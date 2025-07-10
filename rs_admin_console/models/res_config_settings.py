from odoo import models, fields, api
import requests


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    github_token = fields.Char(
        string="GitHub Token",
        config_parameter="client_consola.github_token"
    )
    github_repo = fields.Char(
        string="Repositorio GitHub",
        config_parameter="client_consola.github_repo",
        default="MBP-Odoo/brokerlink"
    )
    github_branch = fields.Char(
        string="Rama GitHub",
        config_parameter="client_consola.github_branch",
        default="main"
    )

    @api.model
    def get_github_settings(self):
        IrConfig = self.env['ir.config_parameter'].sudo()
        return {
            'token': IrConfig.get_param("client_consola.github_token"),
            'repo': IrConfig.get_param("client_consola.github_repo"),
            'branch': IrConfig.get_param("client_consola.github_branch"),
        }

    def action_test_github_connection(self):
        self.ensure_one()
        config = self.get_github_settings()

        if not config['token'] or not config['repo'] or not config['branch']:
            return self._return_message("❌ Faltan parámetros: token, repo o branch", "danger")

        headers = {
            "Authorization": f"token {config['token']}",
            "Accept": "application/vnd.github+json"
        }
        url = f"https://api.github.com/repos/{config['repo']}/commits/{config['branch']}"

        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                sha = response.json().get("sha")
                return self._return_message(f"✅ Conexión exitosa. Último SHA: <code>{sha}</code>", "success")
            else:
                return self._return_message(
                    f"❌ Error {response.status_code}: {response.text}", "danger"
                )
        except Exception as e:
            return self._return_message(f"❌ Error de conexión: {str(e)}", "danger")

    def _return_message(self, message, level):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Prueba de GitHub',
                'message': message,
                'type': level,
                'sticky': False,
            }
        }
