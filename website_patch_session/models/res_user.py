from odoo import models
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)


class ResUsers(models.Model):
    _inherit = "res.users"

    def _check_credentials(self, password, env):
        try:
            result = super()._check_credentials(password, env)
        except AttributeError as e:
            if "'Request' object has no attribute 'session'" in str(e):
                _logger.warning("⚠️ Wishlist falló por falta de session en XML-RPC, se ignora.")
                return True
            raise

        # Ya no necesitas más lógica de wishlist aquí, ya fue manejada arriba
        return result
