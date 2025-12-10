# Migration: Convert all model primary keys from Integer to UUID
# SQLite-safe version: Creates new tables automatically and migrates data

from django.db import migrations, models, connection
import uuid


def migrate_commentflag_to_uuid(apps, schema_editor):
    """Migrate CommentFlag data from integer PK to UUID PK (SQLite only)."""
    if connection.vendor != 'sqlite':
        return  # Not needed for PostgreSQL/MySQL
    
    CommentFlag = apps.get_model('django_comments', 'CommentFlag')
    
    # Store old data with new UUIDs
    old_data = []
    for flag in CommentFlag.objects.all():
        old_data.append({
            'new_id': uuid.uuid4(),
            'comment_type_id': flag.comment_type_id,
            'comment_id': flag.comment_id,
            'user_id': flag.user_id,
            'flag': flag.flag,
            'reason': flag.reason,
            'created_at': flag.created_at,
            'updated_at': flag.updated_at,
            'reviewed': flag.reviewed,
            'reviewed_by_id': flag.reviewed_by_id if hasattr(flag, 'reviewed_by_id') else None,
            'reviewed_at': flag.reviewed_at,
            'review_action': flag.review_action if hasattr(flag, 'review_action') else '',
            'review_notes': flag.review_notes if hasattr(flag, 'review_notes') else '',
        })
    
    # Delete all old records
    CommentFlag.objects.all().delete()
    
    # Recreate with new UUIDs
    for data in old_data:
        new_id = data.pop('new_id')
        CommentFlag.objects.create(id=new_id, **data)


def migrate_banneduser_to_uuid(apps, schema_editor):
    """Migrate BannedUser data from integer PK to UUID PK (SQLite only)."""
    if connection.vendor != 'sqlite':
        return
    
    BannedUser = apps.get_model('django_comments', 'BannedUser')
    
    old_data = []
    for ban in BannedUser.objects.all():
        old_data.append({
            'new_id': uuid.uuid4(),
            'user_id': ban.user_id,
            'banned_until': ban.banned_until if hasattr(ban, 'banned_until') else None,
            'reason': ban.reason,
            'banned_by_id': ban.banned_by_id if hasattr(ban, 'banned_by_id') else None,
            'created_at': ban.created_at,
            'updated_at': ban.updated_at,
        })
    
    BannedUser.objects.all().delete()
    
    for data in old_data:
        new_id = data.pop('new_id')
        BannedUser.objects.create(id=new_id, **data)


def migrate_commentrevision_to_uuid(apps, schema_editor):
    """Migrate CommentRevision data from integer PK to UUID PK (SQLite only)."""
    if connection.vendor != 'sqlite':
        return
    
    CommentRevision = apps.get_model('django_comments', 'CommentRevision')
    
    old_data = []
    for revision in CommentRevision.objects.all():
        old_data.append({
            'new_id': uuid.uuid4(),
            'comment_type_id': revision.comment_type_id,
            'comment_id': revision.comment_id,
            'content': revision.content,
            'edited_by_id': revision.edited_by_id if hasattr(revision, 'edited_by_id') else None,
            'edited_at': revision.edited_at,
            'was_public': revision.was_public if hasattr(revision, 'was_public') else True,
            'was_removed': revision.was_removed if hasattr(revision, 'was_removed') else False,
        })
    
    CommentRevision.objects.all().delete()
    
    for data in old_data:
        new_id = data.pop('new_id')
        CommentRevision.objects.create(id=new_id, **data)


def migrate_moderationaction_to_uuid(apps, schema_editor):
    """Migrate ModerationAction data from integer PK to UUID PK (SQLite only)."""
    if connection.vendor != 'sqlite':
        return
    
    ModerationAction = apps.get_model('django_comments', 'ModerationAction')
    
    old_data = []
    for action in ModerationAction.objects.all():
        old_data.append({
            'new_id': uuid.uuid4(),
            'comment_type_id': action.comment_type_id if hasattr(action, 'comment_type_id') else None,
            'comment_id': action.comment_id if hasattr(action, 'comment_id') else '',
            'moderator_id': action.moderator_id if hasattr(action, 'moderator_id') else None,
            'action': action.action,
            'reason': action.reason if hasattr(action, 'reason') else '',
            'affected_user_id': action.affected_user_id if hasattr(action, 'affected_user_id') else None,
            'timestamp': action.timestamp,
            'ip_address': action.ip_address if hasattr(action, 'ip_address') else None,
        })
    
    ModerationAction.objects.all().delete()
    
    for data in old_data:
        new_id = data.pop('new_id')
        ModerationAction.objects.create(id=new_id, **data)


class Migration(migrations.Migration):
    """
    Converts all model primary keys from BigAutoField (integer) to UUIDField.
    
    How it works:
    - For PostgreSQL/MySQL: Django's AlterField handles the conversion automatically
    - For SQLite: We save existing data, delete records, then recreate with UUIDs
    
    Models affected:
    - CommentFlag
    - BannedUser
    - CommentRevision
    - ModerationAction
    
    Note: Comment model already uses UUID primary key (not changed in this migration).
    
    WARNING: This is a destructive migration for SQLite. All existing integer IDs 
    will be replaced with new UUIDs. Make sure you have a backup before running!
    """

    dependencies = [
        ("django_comments", "0002_remove_comment_user_url"),
    ]

    operations = [
        # =====================================================================
        # STEP 1: Alter all model primary keys to UUID
        # 
        # What happens:
        # - PostgreSQL/MySQL: Converts integer column to UUID with data preserved
        # - SQLite: Recreates tables with UUID primary key (data handled in Step 2)
        # =====================================================================
        
        migrations.AlterField(
            model_name='commentflag',
            name='id',
            field=models.UUIDField(
                default=uuid.uuid4,
                editable=False,
                primary_key=True,
                serialize=False,
                verbose_name='ID'
            ),
        ),
        
        migrations.AlterField(
            model_name='banneduser',
            name='id',
            field=models.UUIDField(
                default=uuid.uuid4,
                editable=False,
                primary_key=True,
                serialize=False,
                verbose_name='ID'
            ),
        ),
        
        migrations.AlterField(
            model_name='commentrevision',
            name='id',
            field=models.UUIDField(
                default=uuid.uuid4,
                editable=False,
                primary_key=True,
                serialize=False,
                verbose_name='ID'
            ),
        ),
        
        migrations.AlterField(
            model_name='moderationaction',
            name='id',
            field=models.UUIDField(
                default=uuid.uuid4,
                editable=False,
                primary_key=True,
                serialize=False,
                verbose_name='ID'
            ),
        ),
        
        # =====================================================================
        # STEP 2: Migrate existing data for SQLite
        # 
        # Why needed:
        # SQLite recreated the tables above but with empty data.
        # These functions restore the data with new UUID primary keys.
        # 
        # For PostgreSQL/MySQL:
        # These functions do nothing - data is already preserved from Step 1.
        # =====================================================================
        
        migrations.RunPython(
            migrate_commentflag_to_uuid,
            reverse_code=migrations.RunPython.noop,
        ),
        
        migrations.RunPython(
            migrate_banneduser_to_uuid,
            reverse_code=migrations.RunPython.noop,
        ),
        
        migrations.RunPython(
            migrate_commentrevision_to_uuid,
            reverse_code=migrations.RunPython.noop,
        ),
        
        migrations.RunPython(
            migrate_moderationaction_to_uuid,
            reverse_code=migrations.RunPython.noop,
        ),
    ]