import contextvars
import json
import re
from django.utils.deprecation import MiddlewareMixin
from django.db.backends.postgresql.base import DatabaseWrapper
from django.db import connection
from django.utils.module_loading import import_string
from django.conf import settings
from urllib.parse import quote
import logging


MAX_CONTEXT_SIZE = 1000000 # ~1MB

bemi_context_var = contextvars.ContextVar('bemi_context')

def get_bemi_context(request):
    func_path = getattr(settings, 'BEMI_CONTEXT_FUNCTION', None)
    if func_path:
        func = import_string(func_path)
        return func(request)
    return {}

class BemiMiddleware(MiddlewareMixin):
    def __init__(self, get_response):
        self.get_response = get_response
        super().__init__(get_response)

    def __call__(self, request):
        try:
            context = get_bemi_context(request)
            bemi_context_var.set(context)
        except Exception as e:
            logging.exception(f"Error while getting Bemi context: {e}")
            bemi_context_var.set({})
        with connection.execute_wrapper(BemiDBWrapper()):
            return self.get_response(request)

class BemiDBWrapper:
    def __call__(self, execute, sql, params, many, context):
        try:
            conn = context["connection"]
            if not isinstance(conn, DatabaseWrapper) or 'postgresql' not in conn.settings_dict['ENGINE']:
                return execute(sql, params, many, context)

            bemi_context = bemi_context_var.get(None)
            if not bemi_context:
                return execute(sql, params, many, context)

            if not isinstance(bemi_context, dict):
                return execute(sql, params, many, context)

            if not re.match(r"(INSERT|UPDATE|DELETE)\s", sql, re.IGNORECASE):
                return execute(sql, params, many, context)

            json_str = json.dumps({ **bemi_context, 'SQL': sql })
            escaped_sql_json = quote(json_str, safe='{},[]:"\'\-/_=()% ')
            escaped_sql_json = escaped_sql_json.replace('*/', '* /').replace('/*', '/ *').replace('--', '- -').replace('%', '%%')

            sql_comment = " /*Bemi " + escaped_sql_json + " Bemi*/"
            # Context too large
            if len(sql_comment.encode('utf-8')) > MAX_CONTEXT_SIZE:
                return execute(sql, params, many, context)

            striped_sql = sql.rstrip()
            if striped_sql[-1] == ";":
                sql_with_comment = striped_sql[:-1] + sql_comment + ";"
            else:
                sql_with_comment = striped_sql + sql_comment
            return execute(sql_with_comment, params, many, context)
        except Exception as e:
            logging.exception(f"Error in BemiDBWrapper while executing SQL: {sql}. Error: {str(e)}")
            return execute(sql, params, many, context)
