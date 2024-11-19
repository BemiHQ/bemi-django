import django
from django.conf import settings
from django.test import SimpleTestCase
from unittest import mock
from django.db.backends.postgresql.base import DatabaseWrapper
from bemi.middleware import (
    BemiDBWrapper,
    bemi_context_var,
)

if not settings.configured:
    settings.configure(
        DEBUG=True,
        SECRET_KEY='your-secret-key',
        DATABASES={
            'default': {
                'ENGINE': 'django.db.backends.postgresql',
                'NAME': ':memory:',
            }
        },
        INSTALLED_APPS=[
            'django.contrib.auth',
            'django.contrib.contenttypes',
            'bemi',
        ],
        MIDDLEWARE=['bemi.BemiMiddleware'],
    )

class TestBemiDBWrapper(SimpleTestCase):
    def setUp(self):
        django.setup()
        self.middleware = BemiDBWrapper()
        self.execute_mock = mock.Mock()
        self.sql = "INSERT INTO table_name (column1) VALUES ('value1');"
        self.params = None
        self.many = False
        self.conn_mock = mock.Mock(spec=DatabaseWrapper)
        self.conn_mock.settings_dict = {'ENGINE': 'django.db.backends.postgresql'}
        self.context = {'connection': self.conn_mock}

    def test_non_postgres_engine(self):
        self.conn_mock.settings_dict['ENGINE'] = 'django.db.backends.sqlite3'
        bemi_context_var.set({'user_id': 1})
        self.middleware(self.execute_mock, self.sql, self.params, self.many, self.context)
        self.execute_mock.assert_called_with(self.sql, self.params, self.many, self.context)

    def test_no_bemi_context(self):
        bemi_context_var.set(None)
        self.middleware(self.execute_mock, self.sql, self.params, self.many, self.context)
        self.execute_mock.assert_called_with(self.sql, self.params, self.many, self.context)

    def test_bemi_context_not_dict(self):
        bemi_context_var.set("invalid_context")
        self.middleware(self.execute_mock, self.sql, self.params, self.many, self.context)
        self.execute_mock.assert_called_with(self.sql, self.params, self.many, self.context)

    def test_non_mutating_sql(self):
        bemi_context_var.set({'user_id': 1})
        select_sql = "SELECT * FROM table_name;"
        self.middleware(self.execute_mock, select_sql, self.params, self.many, self.context)
        self.execute_mock.assert_called_with(select_sql, self.params, self.many, self.context)

    def test_sql_comment_added(self):
        bemi_context_var.set({'user': 'test_user'})
        self.middleware(self.execute_mock, self.sql, self.params, self.many, self.context)
        called_sql = self.execute_mock.call_args[0][0]
        self.assertTrue(called_sql.endswith("Bemi*/;"))

    def test_sql_comment_added(self):
        bemi_context_var.set({'user': 'test_user'})
        self.middleware(self.execute_mock, self.sql, self.params, self.many, self.context)
        called_sql = self.execute_mock.call_args[0][0]
        self.assertTrue(called_sql.endswith("Bemi*/;"))

    def test_sql_comment_not_too_large(self):
        bemi_context_var.set({'user': 'test_user' * 1000})
        with mock.patch('bemi.middleware.MAX_CONTEXT_SIZE', 100):
            self.middleware(self.execute_mock, self.sql, self.params, self.many, self.context)
            self.execute_mock.assert_called_with(self.sql, self.params, self.many, self.context)

    def test_exception_handling(self):
        bemi_context_var.set({'user': 'test_user'})
        with mock.patch('json.dumps', side_effect=Exception('Test exception')):
            self.middleware(self.execute_mock, self.sql, self.params, self.many, self.context)
            self.execute_mock.assert_called_with(self.sql, self.params, self.many, self.context)
