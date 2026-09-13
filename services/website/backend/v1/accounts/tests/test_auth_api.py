from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User

ROOT_PWD = 'Root!pass123'
ADMIN_PWD = 'Admin!pass123'
NEW_ADMIN_PWD = 'SecOps!pass9'


class AuthAPITestsBase(APITestCase):

    def setUp(self):
        self.root = User.objects.create_user(
            username='root', password=ROOT_PWD, role=User.Role.ROOT_ADMIN,
        )
        self.admin = User.objects.create_user(
            username='secops', password=ADMIN_PWD, role=User.Role.ADMIN,
        )

    def token(self, user):
        return str(RefreshToken.for_user(user).access_token)

    def refresh_token(self, user):
        return str(RefreshToken.for_user(user))

    def auth(self, user):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token(user)}')


class LoginMeLogoutTests(AuthAPITestsBase):

    def test_login_success_and_me(self):
        resp = self.client.post('/api/v1/auth/login/',
                                {'username': 'root', 'password': ROOT_PWD}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('access', resp.data)
        self.assertIn('refresh', resp.data)

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.data['access']}")
        me = self.client.get('/api/v1/auth/me/')
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.data['username'], 'root')
        self.assertEqual(me.data['role'], 'root_admin')
        self.assertTrue(me.data['is_root_admin'])
        self.assertNotIn('password', me.data)

    def test_login_wrong_password(self):
        resp = self.client.post('/api/v1/auth/login/',
                                {'username': 'root', 'password': 'bad'}, format='json')
        self.assertEqual(resp.status_code, 401)

    def test_disabled_user_cannot_login(self):
        self.admin.is_active = False
        self.admin.save(update_fields=['is_active'])
        resp = self.client.post('/api/v1/auth/login/',
                                {'username': 'secops', 'password': ADMIN_PWD}, format='json')
        self.assertEqual(resp.status_code, 401)

    def test_anonymous_rejected(self):
        self.assertEqual(self.client.get('/api/v1/auth/me/').status_code, 401)


class DisabledUserTokenTests(AuthAPITestsBase):

    def test_old_access_rejected_after_disabled(self):
        self.auth(self.admin)
        self.assertEqual(self.client.get('/api/v1/auth/me/').status_code, 200)
        # Root 禁用该 admin,其旧 access 立即失效
        self.auth(self.root)
        resp = self.client.patch(f'/api/v1/auth/admins/{self.admin.id}/disable/')
        self.assertEqual(resp.status_code, 200)

        self.auth(self.admin)
        self.assertEqual(self.client.get('/api/v1/auth/me/').status_code, 401)

    def test_refresh_rejected_after_disabled(self):
        refresh = self.refresh_token(self.admin)
        self.admin.is_active = False
        self.admin.save(update_fields=['is_active'])
        resp = self.client.post('/api/v1/auth/refresh/', {'refresh': refresh}, format='json')
        self.assertIn(resp.status_code, (400, 401))


class ChangePasswordTests(AuthAPITestsBase):

    def test_wrong_old_password(self):
        self.auth(self.admin)
        resp = self.client.post('/api/v1/auth/change-password/',
                                {'old_password': 'wrong', 'new_password': 'New!pass123'},
                                format='json')
        self.assertEqual(resp.status_code, 400)

    def test_weak_new_password(self):
        self.auth(self.admin)
        resp = self.client.post('/api/v1/auth/change-password/',
                                {'old_password': ADMIN_PWD, 'new_password': '123'},
                                format='json')
        self.assertEqual(resp.status_code, 400)

    def test_success_blacklists_old_refresh(self):
        refresh = self.refresh_token(self.admin)
        self.auth(self.admin)
        resp = self.client.post('/api/v1/auth/change-password/',
                                {'old_password': ADMIN_PWD, 'new_password': 'New!pass123'},
                                format='json')
        self.assertEqual(resp.status_code, 200)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.check_password('New!pass123'))
        # 旧 refresh 已作废
        blocked = self.client.post('/api/v1/auth/refresh/', {'refresh': refresh}, format='json')
        self.assertIn(blocked.status_code, (400, 401))


class AdminManagementPermissionTests(AuthAPITestsBase):

    def test_admin_cannot_manage_users(self):
        self.auth(self.admin)
        self.assertEqual(self.client.get('/api/v1/auth/admins/').status_code, 403)
        self.assertEqual(self.client.post('/api/v1/auth/admins/', {}, format='json').status_code, 403)
        self.assertEqual(
            self.client.patch(f'/api/v1/auth/admins/{self.admin.id}/disable/').status_code, 403)

    def test_anonymous_cannot_manage_users(self):
        self.assertEqual(self.client.get('/api/v1/auth/admins/').status_code, 401)


class AdminCRUDTests(AuthAPITestsBase):

    def setUp(self):
        super().setUp()
        self.auth(self.root)

    def test_list_excludes_root(self):
        resp = self.client.get('/api/v1/auth/admins/')
        self.assertEqual(resp.status_code, 200)
        usernames = [u['username'] for u in resp.data]
        self.assertIn('secops', usernames)
        self.assertNotIn('root', usernames)

    def test_create_admin(self):
        resp = self.client.post('/api/v1/auth/admins/', {
            'username': 'newadmin', 'password': NEW_ADMIN_PWD,
            'display_name': '新管理员', 'email': 'n@x.com',
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['role'], 'admin')
        self.assertTrue(resp.data['is_active'])
        self.assertNotIn('password', resp.data)
        created = User.objects.get(username='newadmin')
        self.assertTrue(created.check_password(NEW_ADMIN_PWD))
        self.assertEqual(created.role, User.Role.ADMIN)

    def test_create_admin_role_cannot_be_forged(self):
        resp = self.client.post('/api/v1/auth/admins/', {
            'username': 'forged', 'password': NEW_ADMIN_PWD, 'role': 'root_admin',
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(User.objects.get(username='forged').role, User.Role.ADMIN)

    def test_create_admin_weak_password(self):
        resp = self.client.post('/api/v1/auth/admins/', {
            'username': 'weak', 'password': '123',
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_disable_enable_cycle(self):
        resp = self.client.patch(f'/api/v1/auth/admins/{self.admin.id}/disable/')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data['is_active'])
        # 重复禁用
        self.assertEqual(
            self.client.patch(f'/api/v1/auth/admins/{self.admin.id}/disable/').status_code, 400)
        # 启用后可重新登录
        self.assertEqual(
            self.client.patch(f'/api/v1/auth/admins/{self.admin.id}/enable/').status_code, 200)
        login = self.client.post('/api/v1/auth/login/',
                                 {'username': 'secops', 'password': ADMIN_PWD}, format='json')
        self.assertEqual(login.status_code, 200)

    def test_reset_password(self):
        resp = self.client.post(
            f'/api/v1/auth/admins/{self.admin.id}/reset-password/',
            {'new_password': 'Reset!pass9'}, format='json')
        self.assertEqual(resp.status_code, 200)
        old_login = self.client.post('/api/v1/auth/login/',
                                     {'username': 'secops', 'password': ADMIN_PWD}, format='json')
        self.assertEqual(old_login.status_code, 401)
        new_login = self.client.post('/api/v1/auth/login/',
                                     {'username': 'secops', 'password': 'Reset!pass9'}, format='json')
        self.assertEqual(new_login.status_code, 200)

    def test_delete_admin(self):
        resp = self.client.delete(f'/api/v1/auth/admins/{self.admin.id}/')
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(User.objects.filter(id=self.admin.id).exists())

    def test_cannot_manage_root(self):
        self.assertEqual(
            self.client.patch(f'/api/v1/auth/admins/{self.root.id}/disable/').status_code, 400)
        self.assertEqual(
            self.client.patch(f'/api/v1/auth/admins/{self.root.id}/enable/').status_code, 400)
        self.assertEqual(
            self.client.post(f'/api/v1/auth/admins/{self.root.id}/reset-password/',
                             {'new_password': 'Xxx!pass123'}, format='json').status_code, 400)
        self.assertEqual(
            self.client.delete(f'/api/v1/auth/admins/{self.root.id}/').status_code, 400)

    def test_cannot_operate_on_self(self):
        self.assertEqual(
            self.client.patch(f'/api/v1/auth/admins/{self.root.id}/disable/').status_code, 400)
        self.assertEqual(
            self.client.delete(f'/api/v1/auth/admins/{self.root.id}/').status_code, 400)

    def test_target_not_found(self):
        self.assertEqual(self.client.patch('/api/v1/auth/admins/999999/enable/').status_code, 404)
        self.assertEqual(self.client.delete('/api/v1/auth/admins/999999/').status_code, 404)
