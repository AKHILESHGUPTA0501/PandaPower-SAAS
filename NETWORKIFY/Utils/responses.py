"""
JSON response builders. Routes call ok() and fail() so every
response has the same envelope shape:

    { "success": bool, "message": str, "data": Any, "pagination": {...} }
"""

from typing import Any
from flask import jsonify, request
from .constants import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE

def ok(data : Any= None, message : str = 'OK', status : int = 200, **extra) -> tuple:
    payload  = {'success': True, 'message': message}
    if data is not None:
        payload['data'] = data
    payload.update(extra)
    return jsonify(payload), status



def fail(message:str=None, status:int = 400, **extra)-> tuple:
    payload = {'success': False, 'message': message}
    payload.update(extra)
    return jsonify(payload), status



def paginate_query(query, default_per_page : int = DEFAULT_PAGE_SIZE, max_per_page: int = MAX_PAGE_SIZE):
    try:
        page = max(1, int(request.args.get('page',1)))
    except (TypeError, ValueError):
        page = 1
    try:
        per_page = int(request.args.get('per_page', default_per_page))
    except (TypeError, ValueError):
        per_page = default_per_page
    per_page = max(1, min(per_page, max_per_page))
    total = query.count()
    items = query.offset((page -1)*per_page).limit(per_page).all()
    meta = {
        'page': page,
        'per_page': per_page,
        'total': total,
        'pages': (total + per_page -1) // per_page,
    }
    return items, meta