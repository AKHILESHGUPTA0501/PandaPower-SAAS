"""
Common shared schemas: pagination meta, generic API response envelope.
"""
from marshmallow import Schema, fields, validate


class PaginationSchema(Schema):
    """Pagination metadata returned alongside list responses."""
    page     = fields.Integer(required=True)
    per_page = fields.Integer(required=True)
    total    = fields.Integer(required=True)
    pages    = fields.Integer(required=True)


class PaginationQuerySchema(Schema):
    """?page=&per_page= query-string validator."""
    page     = fields.Integer(load_default=1,  validate=validate.Range(min=1))
    per_page = fields.Integer(load_default=20, validate=validate.Range(min=1, max=100))


class ApiResponseSchema(Schema):
    """Standard success envelope."""
    success    = fields.Boolean(required=True)
    message    = fields.String(required=False)
    data       = fields.Raw(required=False)
    pagination = fields.Nested(PaginationSchema, required=False)


class ErrorResponseSchema(Schema):
    """Standard error envelope."""
    success        = fields.Boolean(required=True)
    message        = fields.String(required=True)
    errors         = fields.Dict(keys=fields.String(), values=fields.Raw(), required=False)
    missing_fields = fields.List(fields.String(), required=False)
