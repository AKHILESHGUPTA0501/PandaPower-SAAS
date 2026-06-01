"""
Audit log writer.

Best-effort: writes a row to AuditLog. Failures here NEVER break the
parent request — caught and logged.
"""
import json 
from typing import Any
from flask import request
from extension import db
from Models import AuditLog, AuditAction
from .logger import get_logger


_log = get_logger(__name__)


def log_action(
        action : AuditAction | str,
        *,
        user_id : int| None = None,
        org_id : int | None = None,
        resource_type: str | None =None,
        resource_id : int | None = None,
        status_code : int | None = None,
        details : dict[str, Any] | None = None,
        success : bool = True,
        error_message : str | None = None,
) -> None:
    try:
        if isinstance(action, str):
            action = AuditAction(action)
        ip = None
        ua = None
        method = None
        path = None
        try:
            if request:
                ip = request.headers.get('X_forwared_For', request.remote_addr) or None
                if ip and ',' in ip:
                    ip = ip.split(',', 1)[0].strip()
                ua = (request.headers.get('User-Agent') or '')[:300] or None
                method = request.method
                path = request.path
        except RuntimeError:
            pass
        entry = AuditLog(
            user_id      = user_id,
            org_id       = org_id,
            action       = action,
            resource_type= resource_type,
            resource_id  = resource_id,
            ip_address   = ip,
            user_agent   = ua,
            http_method  = method,
            http_path    = path,
            status_code  = status_code,
            details_json = json.dumps(details, default=str) if details else None,
            success      = success,
            error_message= error_message,
        )    
        db.session.add(entry)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        _log.warning("audit log write failed: %s", e)

def log_failed(action : AuditAction | str, error : str, **kwargs) -> None:
    """Convenience wrapper for failure rows"""
    log_action(action, success= False, error_message= error, **kwargs)


    