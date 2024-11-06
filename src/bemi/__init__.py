from django.utils.deprecation import MiddlewareMixin
from django.db.backends.postgresql.base import DatabaseWrapper
from django.db import connection
from django.utils.module_loading import import_string
from django.conf import settings
import contextvars
import json
import re

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
        context = get_bemi_context(request)
        bemi_context_var.set(context)
        with connection.execute_wrapper(BemiDBWrapper()):
            return self.get_response(request)

class BemiDBWrapper:
    def __call__(self, execute, sql, params, many, context):
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

        sql = sql.rstrip()
        safe_sql = sql.replace('%', '%%')

        json_str = json.dumps({ **bemi_context, 'SQL': safe_sql })
        json_str = json_str.replace('*/', '* /').replace('/*', '/ *').replace('--', '- -')

        sql_comment = " /*Bemi " + json_str + " Bemi*/"

        # Context too large
        if len(sql_comment.encode('utf-8')) > MAX_CONTEXT_SIZE:
            return execute(sql, params, many, context)

        if sql[-1] == ";":
            sql = sql[:-1] + sql_comment + ";"
        else:
            sql = sql + sql_comment

        return execute(sql, params, many, context)

class Bemi:
    @staticmethod
    def migration_up():
        return """
    CREATE OR REPLACE FUNCTION _bemi_row_trigger_func()
        RETURNS TRIGGER
    AS $$
    DECLARE
        _bemi_metadata TEXT;
    BEGIN
        SELECT split_part(split_part(current_query(), '/*Bemi ', 2), ' Bemi*/', 1) INTO _bemi_metadata;
        IF _bemi_metadata <> '' THEN
        PERFORM pg_logical_emit_message(true, '_bemi', _bemi_metadata);
        END IF;

        IF (TG_OP = 'DELETE') THEN
        RETURN OLD;
        ELSE
        RETURN NEW;
        END IF;
    END;
    $$ LANGUAGE plpgsql;

    CREATE OR REPLACE PROCEDURE _bemi_create_triggers()
    AS $$
    DECLARE
        current_tablename TEXT;
    BEGIN
        FOR current_tablename IN
        SELECT tablename FROM pg_tables WHERE schemaname = 'public'
        LOOP
        EXECUTE format(
            'CREATE OR REPLACE TRIGGER _bemi_row_trigger_%s
            BEFORE INSERT OR UPDATE OR DELETE ON %I FOR EACH ROW
            EXECUTE FUNCTION _bemi_row_trigger_func()',
            current_tablename, current_tablename
        );
        END LOOP;
    END;
    $$ LANGUAGE plpgsql;

    CALL _bemi_create_triggers();

    CREATE OR REPLACE FUNCTION _bemi_create_table_trigger_func()
        RETURNS event_trigger
    AS $$
    BEGIN
        CALL _bemi_create_triggers();
    END
    $$ LANGUAGE plpgsql;

    DO $$
    BEGIN
        DROP EVENT TRIGGER IF EXISTS _bemi_create_table_trigger;
        CREATE EVENT TRIGGER _bemi_create_table_trigger ON ddl_command_end WHEN TAG IN ('CREATE TABLE') EXECUTE FUNCTION _bemi_create_table_trigger_func();
    EXCEPTION WHEN insufficient_privilege THEN
        RAISE NOTICE 'Please execute "CALL _bemi_create_triggers();" manually after adding new tables you want to track. (%) %.', SQLSTATE, SQLERRM;
    END
    $$ LANGUAGE plpgsql;
"""

    @staticmethod
    def migration_down():
        return """
    DROP EVENT TRIGGER _bemi_create_table_trigger;
    DROP FUNCTION _bemi_create_table_trigger_func;
    DROP PROCEDURE _bemi_create_triggers;
    DROP FUNCTION _bemi_row_trigger_func CASCADE;
"""
