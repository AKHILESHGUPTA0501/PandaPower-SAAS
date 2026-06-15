"""
Register app-wide error handlers so every error is returned as JSON.
"""

import uuid 
from flask import Flask, g, request
from werkzeug.exceptions import HTTPException
from marshmallow import ValidationError
from sqlalchemy.exc import IntegrityError, OperationalError

from .responses import fail
from .logger import get_logger



_log = get_logger(__name__)


def register_error_handlers(app : Flask) -> None:
    """Attach standard error handlers + request-id middleware."""

    @app.before_request
    def assign_request_id():
        rid = (request.headers.get('X-request-id') or uuid.uuid4().hex[:12])
        g.request_id = rid
        g.user_id = None

    @app.after_request
    def _add_request_id_header(response):
        response.headers['X-request-id'] = getattr(g, 'request_id', '-')
        return response
    @app.errorhandler(ValidationError)
    def _validation_error(err: ValidationError):
        return fail('validation Failed',400, errors = err.messages)
    
    @app.errorhandler(IntegrityError)
    def _integrity(err: IntegrityError):
        _log.warning('DB integrity error :%s ', err)
        from extension import db
        db.session.rollback
        return fail('Data Integrity Error (duplicate or invalid reference)')
    @app.errorhandler(OperationalError)
    def _operational(err : OperationalError):
        _log.error('Db Operational Error: %s', err)
        from extension import db
        db.session.rollback
        return fail('Database Unavailable please retry',503)
    @app.errorhandler(400)
    def _400(_): return fail("Bad Request",400)
    @app.errorhandler(401)
    def _401(_):  return fail("Unauthorized", 401)
    @app.errorhandler(403)
    def _403(_):  return fail("Forbidden", 403)
    @app.errorhandler(404)
    def _404(_):  return fail("Not found", 404)
    @app.errorhandler(405)
    def _405(_):  return fail("Method not allowed", 405)
    @app.errorhandler(413)
    def _413(_):  return fail("Payload too large", 413)
    @app.errorhandler(429)
    def _429(_):  return fail("Too many requests", 429)

    @app.errorhandler(HTTPException)
    def _http(err: HTTPException):
        return fail(err.description or err.name, err.code or 500)
    @app.errorhandler(Exception)
    def _500(err: Exception):
        _log.exception('Unhandled Exception: %s', err)
        from extension import db
        db.session.rollback()
        if app.config.get('DEBUG'):
            return fail(f'Internal Server error ; {err}',500)
        return fail('Internal Server Error')
    