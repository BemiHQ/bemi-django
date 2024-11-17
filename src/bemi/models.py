from django.db import models
from .managers import BemiChangeManager

class BemiChange(models.Model):
    operation = models.CharField(max_length=10)
    table = models.CharField(max_length=255)
    primary_key = models.CharField(max_length=255)
    before = models.JSONField(null=True)
    after = models.JSONField(null=True)
    context = models.JSONField(null=True)
    committed_at = models.DateTimeField()

    objects = BemiChangeManager()

    class Meta:
        db_table = 'changes'
        managed = False
        ordering = ['committed_at']

    def diff(self):
        diff = {}
        before_keys = set(self.before.keys() if self.before else [])
        after_keys = set(self.after.keys() if self.after else [])
        for key in before_keys.union(after_keys):
            before_value = self.before.get(key) if self.before else None
            after_value = self.after.get(key) if self.after else None
            if before_value != after_value:
                diff[key] = [before_value, after_value]
        return diff
