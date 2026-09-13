from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        ROOT_ADMIN = 'root_admin', 'Root Admin'
        ADMIN = 'admin', 'Admin'

    role = models.CharField(
        max_length=16, choices=Role.choices, default=Role.ADMIN,
    )
    display_name = models.CharField(max_length=64, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def is_root_admin(self) -> bool:
        return self.role == self.Role.ROOT_ADMIN

    def __str__(self):
        return self.display_name or self.username
