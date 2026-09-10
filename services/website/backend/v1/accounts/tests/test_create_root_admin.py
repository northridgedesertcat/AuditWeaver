from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from accounts.models import User


class CreateRootAdminCommandTests(TestCase):

    def _run(self, username='root', password='Str0ng!pass', email='r@x.com'):
        with patch('accounts.management.commands.create_root_admin.getpass.getpass',
                   side_effect=[password, password]), \
             patch('builtins.input', return_value=username):
            call_command('create_root_admin', email=email)

    def test_creates_root_admin_with_hashed_password(self):
        self._run()
        user = User.objects.get(username='root')
        self.assertEqual(user.role, User.Role.ROOT_ADMIN)
        self.assertTrue(user.check_password('Str0ng!pass'))
        self.assertNotIn('Str0ng!pass', user.password)
        self.assertTrue(user.password.startswith('pbkdf2_'))

    def test_idempotent_second_root_rejected(self):
        self._run()
        with self.assertRaises(CommandError):
            self._run(username='root2')
        self.assertEqual(User.objects.filter(role=User.Role.ROOT_ADMIN).count(), 1)

    def test_weak_password_rejected(self):
        with self.assertRaises(CommandError):
            self._run(username='weakroot', password='123')
        self.assertFalse(User.objects.filter(username='weakroot').exists())

    def test_password_mismatch_rejected(self):
        with patch('accounts.management.commands.create_root_admin.getpass.getpass',
                   side_effect=['Str0ng!pass', 'Other!pass9']), \
             patch('builtins.input', return_value='mismatch'):
            with self.assertRaises(CommandError):
                call_command('create_root_admin')
        self.assertFalse(User.objects.filter(username='mismatch').exists())

    def test_duplicate_username_rejected(self):
        self._run(username='dup')
        with self.assertRaises(CommandError):
            self._run(username='dup')
