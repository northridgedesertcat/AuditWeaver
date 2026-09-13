from django.db import migrations, models

# 存量角色映射:
#   admin   -> root_admin  (现存唯一初始管理员升级为 Root Admin)
#   analyst -> admin
#   viewer  -> admin
ROLE_MAP = {
    'admin': 'root_admin',
    'analyst': 'admin',
    'viewer': 'admin',
}


def forwards(apps, schema_editor):
    User = apps.get_model('accounts', 'User')
    for old_role, new_role in ROLE_MAP.items():
        User.objects.filter(role=old_role).update(role=new_role)


def backwards(apps, schema_editor):
    # 无法精确还原 analyst/viewer,统一回退为 admin,仅保兼容
    User = apps.get_model('accounts', 'User')
    User.objects.filter(role='root_admin').update(role='admin')


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='role',
            field=models.CharField(
                choices=[('root_admin', 'Root Admin'), ('admin', 'Admin')],
                default='admin',
                max_length=16,
            ),
        ),
        migrations.RunPython(forwards, backwards),
    ]
