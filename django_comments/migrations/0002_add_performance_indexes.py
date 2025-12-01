# Generated migration for adding performance indexes
# Place this in: django_comments/migrations/0002_add_performance_indexes.py

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('django_comments', '0001_initial'),
    ]

    operations = [
        # Add composite index for common query patterns
        migrations.AddIndex(
            model_name='comment',
            index=models.Index(
                fields=['is_public', 'is_removed', 'created_at'],
                name='django_comm_public_status_created_idx'
            ),
        ),
        
        # Add index for filtering public comments on specific objects
        migrations.AddIndex(
            model_name='comment',
            index=models.Index(
                fields=['content_type', 'object_id', 'is_public', 'is_removed'],
                name='django_comm_ct_obj_public_idx'
            ),
        ),
        
        # Add index for user's comments ordered by date
        migrations.AddIndex(
            model_name='comment',
            index=models.Index(
                fields=['user', 'created_at'],
                name='django_comm_user_created_idx'
            ),
        ),
        
        # Add index for thread queries
        migrations.AddIndex(
            model_name='comment',
            index=models.Index(
                fields=['thread_id', 'path'],
                name='django_comm_thread_path_idx'
            ),
        ),
        
        # Add index for moderation queue (non-public, not removed)
        migrations.AddIndex(
            model_name='comment',
            index=models.Index(
                fields=['is_public', 'is_removed', 'created_at'],
                condition=models.Q(is_public=False, is_removed=False),
                name='django_comm_moderation_queue_idx'
            ),
        ),
    ]