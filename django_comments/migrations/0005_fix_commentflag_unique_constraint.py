from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('django_comments', '0004_alter_commentflag_user_banneduser_unique_banned_user'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='commentflag',
            name='unique_comment_flag_per_user',
        ),
        migrations.AddConstraint(
            model_name='commentflag',
            constraint=models.UniqueConstraint(
                fields=('comment_type', 'comment_id', 'flag'),
                name='unique_comment_flag_per_user',
                violation_error_message='This comment has already been flagged with this flag type.',
            ),
        ),
    ]