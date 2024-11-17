from django.db import models
from django.db.models.expressions import RawSQL, ExpressionWrapper
from django.db.models import BooleanField

class BemiChangeQuerySet(models.QuerySet):
    def before(self, data):
        return self.filter(before__contains=data)

    def before_not(self, data):
        return self.exclude(before__contains=data)

    def after(self, data):
        return self.filter(after__contains=data)

    def after_not(self, data):
        return self.exclude(after__contains=data)

    def context(self, data):
        return self.filter(context__contains=data)

    def context_not(self, data):
        return self.exclude(context__contains=data)

    def created(self):
        return self.filter(operation='CREATE')

    def updated(self):
        return self.filter(operation='UPDATE')

    def deleted(self):
        return self.filter(operation='DELETE')

    def asc(self):
        return self.order_by('committed_at')

    def desc(self):
        return self.order_by('-committed_at')

    def field_changed(self, table, primary_key, field_name):
        """
        Filters changes where the specified field was modified for a specific table and primary key.
        """
        condition = ExpressionWrapper(
            RawSQL("(before -> %s) IS DISTINCT FROM (after -> %s)", [field_name, field_name]),
            output_field=BooleanField()
        )
        return self.annotate(field_changed=condition).filter(
            field_changed=True,
            table=table,
            primary_key=str(primary_key)
        )
