"""
Structured logging configuration.

Call `configure_logging(app)` from create_app() once, then use
`get_logger(__name__)` everywhere else.
"""
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from  flask import Flask, has_request_context, request, g



_LOG_FORMAT = (
    "%(asctime)s [%(levelname)s] %(name)s "
    "[%(request_id)s]  %(message)s"
)


class _RequestContextFilter(logging.Filter):
    """Attach request_id and user_id to log records if inside a request."""
    def filter(self, record: logging.LogRecord)-> bool:
        if has_request_context():
            record.request_id = getattr(g, 'request_id', '-')
            record.user_id = getattr(g, 'user_id', '-')
            record.path = request.path 
            record.method = request.method 
        else:
            record.request_id = '-'
            record.user_id = '-'
            record.path       = "-"
            record.method     = "-"
        return True
    
def configure_logging(app: Flask) -> None:
    level_name =(app.config.get('LOG_LEVEL')
                or os.getenv('LOG_LEVEL', 'INFO')).upper()
    level = getattr(logging, level_name, logging.INFO)
    root = logging.getLogger()
    root.setLevel(level)
    for h in list(root.handlers):
        root.removeHandler(h)
    formatter = logging.Formatter(_LOG_FORMAT)
    ctx_filter = _RequestContextFilter()
    
    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(formatter)
    stream.addFilter(ctx_filter)
    root.addHandler(stream)

    log_file = app.config.get('LOG_FILE') or os.getenv('LOG_FILE')
    if log_file:
        os.makedirs(os.path.dirname(log_file) or '.', exist_ok= True)
        fh= RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount= 5)
        fh.setFormatter(formatter)
        fh.addFilter(ctx_filter)
        root.addHandler(fh)

    for name in ("werkzeug", "engineio.server", "socketio.server"):
        logging.getLogger(name).setLevel(logging.WARNING)
    app.logger.setLevel(level)

def get_logger(name :str) -> logging.Logger:
    return logging.getLogger(name)

