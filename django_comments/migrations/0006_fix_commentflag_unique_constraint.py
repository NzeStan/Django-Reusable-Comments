# Generated migration to fix CommentFlag unique constraint
# 
# IMPORTANT: This migration fixes the unique constraint to allow multiple users
# to flag the same comment with the same flag type. The constraint should prevent
# a single user from flagging the same comment multiple times with the same flag type,
# NOT prevent multiple different users from using the same flag type.
#
# Place this file in: django_comments/migrations/0006_fix_commentflag_unique_constraint.py

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('django_comments', '0005_fix_commentflag_unique_constraint'),
    ]

    operations = [
        # Remove the incorrect constraint
        migrations.RemoveConstraint(
            model_name='commentflag',
            name='unique_comment_flag_per_user',
        ),
        # Add the CORRECT constraint that includes 'user'
        # This allows multiple users to flag the same comment with the same flag type
        # But prevents a single user from flagging the same comment multiple times
        migrations.AddConstraint(
            model_name='commentflag',
            constraint=models.UniqueConstraint(
                fields=('comment_type', 'comment_id', 'user', 'flag'),
                name='unique_comment_user_flag',
                violation_error_message='You have already flagged this comment with this flag type.',
            ),
        ),
    ]