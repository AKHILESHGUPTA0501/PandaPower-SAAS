"""
Socket.IO namespace `/analysis`.

Client lifecycle
----------------
  1. Client opens a Socket.IO connection with the JWT in the
     `auth.token` field.
  2. On `connect`, the server validates the token, joins the client
     to the per-user room "user_<id>", and emits `connected`.
  3. The client can also explicitly join/leave job-specific rooms
     ("job_<id>") via `subscribe_job` / `unsubscribe_job` events,
     useful for shared dashboards.
  4. On `disconnect` everything is cleaned up automatically.

Auth
----
We accept the JWT in `auth.token` (the standard way for
Flask-SocketIO 5+). Falls back to the `Authorization` header when
present.
"""
from flask import request
from flask_socketio import (
    SocketIO,
    emit,
    join_room,
    leave_room,
    disconnect,
)
from extension import db
from flask_jwt_extended import decode_token
from Models import Users, AnalysisJob
from Utils.constants import SIO_NAMESPACE
from Utils.logger import get_logger
from .events import user_room


_log = get_logger(__name__)


def _resolve_user_from_token(token : str | None) -> Users | None :
    if not token:
        return None
    try:
        if token.lower().startswith('bearer '):
            token = token.split(" ",1)[1]
        decoded = decode_token(token)
    except Exception as e:
        _log.debug('socket token decode failed: %s', e)
        return None
    uid = decoded.get('sub')
    if uid is None:
        return None
    try:
        return db.session.get(Users, int(uid))
    except (TypeError,ValueError):
        return None
    
def register_handlers(socketio: SocketIO) -> None:
    @socketio.on('connect', namespace= SIO_NAMESPACE)
    def on_connect(auth):
        token= None
        if isinstance(auth, dict):
            token = auth.get('token')
        if not token:
            try:
                token = request.args.gte('token') or \
                        request.headers.get('Authorization')
            except RuntimeError:
                token = None
        user = _resolve_user_from_token(token)
        if user is None or not user.is_active:
            _log.info('socket connect rejected (sid = %s)', request.sid)
            emit('error', {'message':'Unauthorized'})
            disconnect()
            return False
        join_room(user_room(user.id))
        _log.info('socket connect user = %s sid =%s', user.id, request.sid)
        emit("connected", {
            "user_id":   user.id,
            "username":  user.username,
            "room":      user_room(user.id),
        })
        return True
    @socketio.on('disconnect', namespace= SIO_NAMESPACE)
    def on_disconnect():
        _log.info('Socket disconnect sid = %s', request.sid)
    
    @socketio.on('ping_check', namespace= SIO_NAMESPACE)
    def on_ping(_data = None):
        emit('pong', {'ok': True})

    @socketio.on('subscribe_job', namespace= SIO_NAMESPACE)
    def on_subscribe_job(data):
        """
        Join a job-specific room to receive updates even if the job
        was launched by a colleague (must be your job, or admin).
        """
        token = (data or {}).get('token')
        user = _resolve_user_from_token(token) if token else None
        if user is None:
            emit('error', {'message': 'Unauthorized'})
            return
        job_id = (data or {}).get('job_id')
        if not job_id:
            emit('error', {'message':'Job_id required'})
            return
        job = db.session.get(AnalysisJob, int(job_id))
        if job is None:
            emit('error', {'message': 'Job not found'})
            return
        if job.user_id != user.id and not user.is_admin:
            emit('error', {'message': 'Forbidden'})
            return
        room = f'job_{job_id}'
        join_room(room)
        emit('subscribed', {'job_id':int(job_id), 'room': room})

    @socketio.on('unsubscribe_job', namespace= SIO_NAMESPACE)
    def on_unsubscribe_job(data):
        job_id = (data or {}).get('job_id')
        if job_id:
            leave_room(f'job_{job_id}')
            emit('Unsubscribed', {'job_id':int(job_id)})
            