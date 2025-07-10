import logging
from odoo import models, api
from odoo.http import request

_logger = logging.getLogger(__name__)


class Website(models.Model):
    _inherit = 'website'

    @api.model
    def get_current_website(self, fallback=True):
        """Versión segura de get_current_website para evitar errores en llamadas XML-RPC/API."""
        is_frontend_request = bool(request and getattr(request, 'is_frontend', False))

        if not request or not hasattr(request, 'session'):
            _logger.debug("⚠️ get_current_website llamado sin request.session (probablemente XML-RPC, API o cron)")

        # Validación segura de session
        if request and hasattr(request, 'session') and request.session.get('force_website_id'):
            website_id = self.browse(request.session['force_website_id']).exists()
            if not website_id:
                # Evita error si el sitio web en sesión ya no existe
                request.session.pop('force_website_id', None)
            else:
                return website_id

        website_id = self.env.context.get('website_id')
        if website_id:
            return self.browse(website_id)

        if not is_frontend_request and not fallback:
            return self.browse(False)

        # Intentar obtener el dominio desde la request
        domain_name = ''
        if request and hasattr(request, 'httprequest'):
            domain_name = request.httprequest.host or ''
        website_id = self.sudo()._get_current_website_id(domain_name, fallback=fallback)
        return self.browse(website_id)
