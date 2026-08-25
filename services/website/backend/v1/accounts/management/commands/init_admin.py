from django.core.management.base import BaseCommand

from common.env import (
    INITIAL_ADMIN_EMAIL,
    INITIAL_ADMIN_PASSWORD,
    INITIAL_ADMIN_USERNAME,
)

from accounts.models import User


class Command(BaseCommand):
    help = '幂等创建初始管理员账号'

    def handle(self, *args, **opts):
        username = INITIAL_ADMIN_USERNAME
        if User.objects.filter(username=username).exists():
            self.stdout.write(f'admin "{username}" already exists, skip')
            return
        User.objects.create_superuser(
            username=username,
            email=INITIAL_ADMIN_EMAIL,
            password=INITIAL_ADMIN_PASSWORD,
            role=User.Role.ADMIN,
        )
        self.stdout.write(self.style.SUCCESS(f'created admin "{username}"'))
