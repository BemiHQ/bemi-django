from django.apps import apps


class BemiRecordMixin:
    def bemi_changes(self, field_name=None):
        BemiChange = apps.get_model('bemi', 'BemiChange')
        changes = BemiChange.objects.filter(
            table=self._meta.db_table,
            primary_key=str(getattr(self, self._meta.pk.name))
        )
        if field_name:
            changes = changes.field_changed(self._meta.db_table, str(getattr(self, self._meta.pk.name)), field_name)
        return changes

