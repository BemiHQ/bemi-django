from django.db import models
from .querysets import BemiChangeQuerySet

BemiChangeManager = models.Manager.from_queryset(BemiChangeQuerySet)
