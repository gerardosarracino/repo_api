from odoo.addons.base.models import ir_qweb as base_ir_qweb
import logging

_logger = logging.getLogger(__name__)

def safe_prepare_environment(self, values):
    try:
        from odoo.http import request
        safe_debug = ''
        if request and hasattr(request, 'session') and request.session:
            safe_debug = getattr(request.session, 'debug', '')
        else:
            _logger.debug("🔧 ir.qweb parche monkey: sin request.session activa o válida, debug desactivado.")
    except Exception as e:
        safe_debug = ''
        _logger.debug(f"🔧 ir.qweb parche monkey: excepción inesperada ({e}), debug desactivado.")

    values['debug'] = safe_debug
    return original_prepare_environment(self, values)

