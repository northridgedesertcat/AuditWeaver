from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = 'admin', '管理员'
        ANALYST = 'analyst', '分析师'
        VIEWER = 'viewer', '只读'

    role = models.CharField(
        max_length=16, choices=Role.choices, default=Role.ADMIN,
    )
    display_name = models.CharField(max_length=64, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.display_name or self.username
