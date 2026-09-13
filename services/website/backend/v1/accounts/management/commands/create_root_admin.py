import getpass

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from accounts.models import User


class Command(BaseCommand):
    help = '交互式创建(唯一的)Root Admin;密码经 Django 哈希入库,不写明文'

    def add_arguments(self, parser):
        parser.add_argument('--username', help='登录用户名(不传则交互输入)')
        parser.add_argument('--email', default='', help='邮箱(可选)')

    def handle(self, *args, **opts):
        # 单 Root 保证:已存在 Root Admin 则拒绝
        if User.objects.filter(role=User.Role.ROOT_ADMIN).exists():
            raise CommandError('Root Admin 已存在,本命令幂等,不可创建第二个')

        username = opts.get('username')
        if not username:
            username = input('Root Admin 用户名: ').strip()
        if not username:
            raise CommandError('用户名不能为空')
        if User.objects.filter(username=username).exists():
            raise CommandError(f'用户名 "{username}" 已存在')

        email = opts.get('email') or ''

        # 密码输入两次确认,输入内容不回显
        password = getpass.getpass('密码: ')
        if not password:
            raise CommandError('密码不能为空')
        confirm = getpass.getpass('再次输入密码: ')
        if password != confirm:
            raise CommandError('两次输入的密码不一致')

        # 走 Django 标准密码强度校验
        user = User(username=username, email=email, role=User.Role.ROOT_ADMIN)
        try:
            validate_password(password, user=user)
        except ValidationError as e:
            raise CommandError('密码强度不足: %s' % '; '.join(e.messages))

        user.set_password(password)
        user.save()
        self.stdout.write(self.style.SUCCESS(f'Root Admin "{username}" 创建成功'))
