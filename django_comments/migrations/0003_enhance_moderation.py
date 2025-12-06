# Generated migration - save as django_comments/migrations/0003_enhance_moderation.py
# Run: python manage.py migrate django_comments

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('django_comments', '0002_alter_uuidcomment_parent'),  # Adjust to your latest migration
    ]

    operations = [
        # ===================================================================
        # CREATE NEW MODELS
        # ===================================================================
        
        migrations.CreateModel(
            name='BannedUser',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('banned_until', models.DateTimeField(blank=True, help_text='Leave empty for permanent ban', null=True, verbose_name='Banned Until')),
                ('reason', models.TextField(help_text='Reason for banning this user', verbose_name='Reason')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Created at')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Updated at')),
                ('banned_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='users_banned', to=settings.AUTH_USER_MODEL, verbose_name='Banned By')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='comment_bans', to=settings.AUTH_USER_MODEL, verbose_name='User')),
            ],
            options={
                'verbose_name': 'Banned User',
                'verbose_name_plural': 'Banned Users',
                'ordering': ['-created_at'],
            },
        ),
        
        migrations.CreateModel(
            name='CommentRevision',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('comment_id', models.TextField(verbose_name='Comment ID')),
                ('content', models.TextField(help_text='Previous version of comment content', verbose_name='Content')),
                ('edited_at', models.DateTimeField(auto_now_add=True, verbose_name='Edited At')),
                ('was_public', models.BooleanField(default=True, verbose_name='Was Public')),
                ('was_removed', models.BooleanField(default=False, verbose_name='Was Removed')),
                ('comment_type', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='contenttypes.contenttype', verbose_name='Comment Type')),
                ('edited_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, verbose_name='Edited By')),
            ],
            options={
                'verbose_name': 'Comment Revision',
                'verbose_name_plural': 'Comment Revisions',
                'ordering': ['-edited_at'],
            },
        ),
        
        migrations.CreateModel(
            name='ModerationAction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('comment_id', models.TextField(blank=True, verbose_name='Comment ID')),
                ('action', models.CharField(choices=[('approved', 'Approved'), ('rejected', 'Rejected'), ('deleted', 'Deleted'), ('edited', 'Edited'), ('flagged', 'Flagged'), ('unflagged', 'Unflagged'), ('banned_user', 'Banned User'), ('unbanned_user', 'Unbanned User')], max_length=20, verbose_name='Action')),
                ('reason', models.TextField(blank=True, help_text='Reason for this action', verbose_name='Reason')),
                ('timestamp', models.DateTimeField(auto_now_add=True, verbose_name='Timestamp')),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True, verbose_name='IP Address')),
                ('affected_user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='moderation_actions_received', to=settings.AUTH_USER_MODEL, verbose_name='Affected User')),
                ('comment_type', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='contenttypes.contenttype', verbose_name='Comment Type')),
                ('moderator', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='moderation_actions', to=settings.AUTH_USER_MODEL, verbose_name='Moderator')),
            ],
            options={
                'verbose_name': 'Moderation Action',
                'verbose_name_plural': 'Moderation Actions',
                'ordering': ['-timestamp'],
            },
        ),
        
        # ===================================================================
        # UPDATE CommentFlag MODEL
        # ===================================================================
        
        # Add new fields to CommentFlag
        migrations.AddField(
            model_name='commentflag',
            name='reviewed',
            field=models.BooleanField(default=False, help_text='Whether this flag has been reviewed by a moderator', verbose_name='Reviewed'),
        ),
        migrations.AddField(
            model_name='commentflag',
            name='reviewed_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Reviewed At'),
        ),
        migrations.AddField(
            model_name='commentflag',
            name='review_action',
            field=models.CharField(blank=True, choices=[('dismissed', 'Dismissed'), ('actioned', 'Actioned')], max_length=20, verbose_name='Review Action'),
        ),
        migrations.AddField(
            model_name='commentflag',
            name='review_notes',
            field=models.TextField(blank=True, verbose_name='Review Notes'),
        ),
        migrations.AddField(
            model_name='commentflag',
            name='reviewed_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='flags_reviewed', to=settings.AUTH_USER_MODEL, verbose_name='Reviewed By'),
        ),
        
        # Update flag choices (expand from 4 to 10 options)
        migrations.AlterField(
            model_name='commentflag',
            name='flag',
            field=models.CharField(
                choices=[
                    ('spam', 'Spam'),
                    ('harassment', 'Harassment'),
                    ('hate_speech', 'Hate Speech'),
                    ('violence', 'Violence/Threats'),
                    ('sexual', 'Sexual Content'),
                    ('misinformation', 'Misinformation'),
                    ('off_topic', 'Off Topic'),
                    ('offensive', 'Offensive'),
                    ('inappropriate', 'Inappropriate'),
                    ('other', 'Other'),
                ],
                db_index=True,
                default='other',
                max_length=30,
                verbose_name='Flag'
            ),
        ),
        
        # ===================================================================
        # ADD INDEXES
        # ===================================================================
        
        migrations.AddIndex(
            model_name='banneduser',
            index=models.Index(fields=['user', 'banned_until'], name='django_comm_user_id_ban_idx'),
        ),
        
        migrations.AddIndex(
            model_name='commentrevision',
            index=models.Index(fields=['comment_type', 'comment_id'], name='commentrev_comment_idx'),
        ),
        migrations.AddIndex(
            model_name='commentrevision',
            index=models.Index(fields=['edited_at'], name='commentrev_edited_idx'),
        ),
        
        migrations.AddIndex(
            model_name='moderationaction',
            index=models.Index(fields=['comment_type', 'comment_id'], name='modaction_comment_idx'),
        ),
        migrations.AddIndex(
            model_name='moderationaction',
            index=models.Index(fields=['moderator', 'action'], name='modaction_mod_idx'),
        ),
        migrations.AddIndex(
            model_name='moderationaction',
            index=models.Index(fields=['timestamp'], name='modaction_time_idx'),
        ),
        
        migrations.AddIndex(
            model_name='commentflag',
            index=models.Index(fields=['reviewed', 'created_at'], name='commentflag_review_idx'),
        ),
    ]