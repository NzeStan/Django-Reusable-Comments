"""
Comprehensive Test Suite for django_comments/tasks.py

Tests cover:
✅ Task Module Loading
✅ Successful Notification Dispatching
✅ Error Handling (object not found, email failures)
✅ Task Parameter Handling
✅ Integration with Notification Service
✅ Edge Cases & Real-world Scenarios
✅ All 8 Background Tasks

Note: Tasks are plain functions executed synchronously in tests.
All notification services are mocked, so no signal interference occurs.
"""
import uuid
from datetime import timedelta
from threading import Thread
from unittest.mock import Mock, patch, MagicMock, call
from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from django_comments.conf import comments_settings
from django_comments.models import BannedUser, CommentFlag
from django_comments.tests.base import BaseCommentTestCase

# Import tasks module
try:
    from django_comments import tasks
    TASKS_MODULE_AVAILABLE = True
except ImportError:
    TASKS_MODULE_AVAILABLE = False
    tasks = None

User = get_user_model()


# ============================================================================
# TASK MODULE LOADING TESTS
# ============================================================================

class TaskModuleTests(TestCase):
    """Test task module loads correctly without any external dependencies."""

    def test_tasks_module_is_importable(self):
        """Test tasks module always loads successfully."""
        self.assertTrue(TASKS_MODULE_AVAILABLE)
        self.assertIsNotNone(tasks)

    def test_all_task_functions_exist(self):
        """Test all expected task functions are defined."""
        if not TASKS_MODULE_AVAILABLE:
            self.skipTest("Tasks module not available")

        expected_tasks = [
            'notify_new_comment_task',
            'notify_comment_reply_task',
            'notify_comment_approved_task',
            'notify_comment_rejected_task',
            'notify_moderators_task',
            'notify_moderators_of_flag_task',
            'notify_auto_hide_task',
            'notify_user_banned_task',
            'notify_user_unbanned_task',
        ]
        for task_name in expected_tasks:
            self.assertTrue(
                hasattr(tasks, task_name),
                f"Task function '{task_name}' not found in tasks module"
            )
            self.assertTrue(callable(getattr(tasks, task_name)))

    def test_run_in_thread_helper_exists(self):
        """Test the _run_in_thread helper is available."""
        if not TASKS_MODULE_AVAILABLE:
            self.skipTest("Tasks module not available")

        self.assertTrue(hasattr(tasks, '_run_in_thread'))

    def test_threading_is_used(self):
        """Test that threading.Thread is imported in tasks module."""
        import django_comments.tasks as tasks_module
        import inspect
        source = inspect.getfile(tasks_module)
        # Verify the module imports Thread
        with open(source) as f:
            content = f.read()
        self.assertIn('from threading import Thread', content)


# ============================================================================
# NEW COMMENT TASK TESTS
# ============================================================================

class NotifyNewCommentTaskTests(BaseCommentTestCase):
    """Test notify_new_comment_task."""

    def setUp(self):
        super().setUp()
        if not TASKS_MODULE_AVAILABLE:
            self.skipTest("Tasks module not available")
        mail.outbox = []

    def test_notify_new_comment_task_success(self):
        """Test successful new comment notification task."""
        comment = self.create_comment(user=self.regular_user)

        with patch('django_comments.notifications.notification_service') as mock_service:
            tasks.notify_new_comment_task(str(comment.pk))

            mock_service.notify_new_comment.assert_called_once_with(comment)

    def test_notify_new_comment_task_comment_not_found(self):
        """Test task handles comment not found gracefully (logs error, no exception)."""
        fake_uuid = str(uuid.uuid4())

        with self.assertLogs(comments_settings.LOGGER_NAME, level='ERROR') as logs:
            # Should NOT raise an exception
            tasks.notify_new_comment_task(fake_uuid)

        self.assertTrue(any('not found' in log for log in logs.output))

    def test_notify_new_comment_task_with_valid_uuid(self):
        """Test task works with valid UUID string."""
        comment = self.create_comment(content="Test notification")

        with patch('django_comments.notifications.notification_service') as mock_service:
            tasks.notify_new_comment_task(str(comment.pk))

            self.assertEqual(mock_service.notify_new_comment.call_count, 1)
            called_comment = mock_service.notify_new_comment.call_args[0][0]
            self.assertEqual(called_comment.pk, comment.pk)

    def test_notify_new_comment_task_logs_error_on_exception(self):
        """Test task logs error when notification service raises an exception."""
        comment = self.create_comment(user=self.regular_user)

        with patch('django_comments.notifications.notification_service') as mock_service:
            mock_service.notify_new_comment.side_effect = Exception("Email server down")

            with self.assertLogs(comments_settings.LOGGER_NAME, level='ERROR') as logs:
                # Should NOT raise an exception — it should be caught and logged
                tasks.notify_new_comment_task(str(comment.pk))

            self.assertTrue(any('Failed to send new comment notification' in log
                                for log in logs.output))


# ============================================================================
# COMMENT REPLY TASK TESTS
# ============================================================================

class NotifyCommentReplyTaskTests(BaseCommentTestCase):
    """Test notify_comment_reply_task."""

    def setUp(self):
        super().setUp()
        if not TASKS_MODULE_AVAILABLE:
            self.skipTest("Tasks module not available")
        mail.outbox = []

    def test_notify_comment_reply_task_success(self):
        """Test successful comment reply notification task."""
        parent = self.create_comment(
            content="Parent comment",
            user=self.regular_user
        )
        reply = self.create_comment(
            content="Reply comment",
            parent=parent,
            user=self.staff_user
        )

        with patch('django_comments.notifications.notification_service') as mock_service:
            tasks.notify_comment_reply_task(str(reply.pk), str(parent.pk))

            mock_service.notify_comment_reply.assert_called_once_with(reply, parent)

    def test_notify_comment_reply_task_comment_not_found(self):
        """Test task handles comment not found gracefully."""
        fake_reply_id = str(uuid.uuid4())
        fake_parent_id = str(uuid.uuid4())

        with self.assertLogs(comments_settings.LOGGER_NAME, level='ERROR') as logs:
            tasks.notify_comment_reply_task(fake_reply_id, fake_parent_id)

        self.assertTrue(len(logs.output) > 0)

    def test_notify_comment_reply_task_parent_not_found(self):
        """Test task handles parent comment not found gracefully."""
        reply = self.create_comment(content="Reply")
        fake_parent_id = str(uuid.uuid4())

        with self.assertLogs(comments_settings.LOGGER_NAME, level='ERROR') as logs:
            tasks.notify_comment_reply_task(str(reply.pk), fake_parent_id)

        self.assertTrue(len(logs.output) > 0)


# ============================================================================
# COMMENT APPROVAL TASK TESTS
# ============================================================================

class NotifyCommentApprovedTaskTests(BaseCommentTestCase):
    """Test notify_comment_approved_task."""

    def setUp(self):
        super().setUp()
        if not TASKS_MODULE_AVAILABLE:
            self.skipTest("Tasks module not available")
        mail.outbox = []

    def test_notify_comment_approved_task_success(self):
        """Test successful comment approval notification task."""
        comment = self.create_comment(
            user=self.regular_user,
            is_public=False
        )

        with patch('django_comments.notifications.notification_service') as mock_service:
            tasks.notify_comment_approved_task(str(comment.pk), self.staff_user.pk)

            self.assertEqual(mock_service.notify_comment_approved.call_count, 1)
            call_args = mock_service.notify_comment_approved.call_args[0]
            self.assertEqual(call_args[0].pk, comment.pk)
            self.assertEqual(call_args[1].pk, self.staff_user.pk)

    def test_notify_comment_approved_task_without_moderator(self):
        """Test approval notification without moderator."""
        comment = self.create_comment(is_public=False)

        with patch('django_comments.notifications.notification_service') as mock_service:
            tasks.notify_comment_approved_task(str(comment.pk), None)

            call_args = mock_service.notify_comment_approved.call_args[0]
            self.assertIsNone(call_args[1])

    def test_notify_comment_approved_task_comment_not_found(self):
        """Test task handles comment not found gracefully."""
        fake_uuid = str(uuid.uuid4())

        with self.assertLogs(comments_settings.LOGGER_NAME, level='ERROR') as logs:
            tasks.notify_comment_approved_task(fake_uuid, self.staff_user.pk)

        self.assertTrue(len(logs.output) > 0)


# ============================================================================
# COMMENT REJECTION TASK TESTS
# ============================================================================

class NotifyCommentRejectedTaskTests(BaseCommentTestCase):
    """Test notify_comment_rejected_task."""

    def setUp(self):
        super().setUp()
        if not TASKS_MODULE_AVAILABLE:
            self.skipTest("Tasks module not available")
        mail.outbox = []

    def test_notify_comment_rejected_task_success(self):
        """Test successful comment rejection notification task."""
        comment = self.create_comment(
            user=self.regular_user,
            is_public=True
        )

        with patch('django_comments.notifications.notification_service') as mock_service:
            tasks.notify_comment_rejected_task(str(comment.pk), self.staff_user.pk)

            self.assertEqual(mock_service.notify_comment_rejected.call_count, 1)
            call_args = mock_service.notify_comment_rejected.call_args[0]
            self.assertEqual(call_args[0].pk, comment.pk)
            self.assertEqual(call_args[1].pk, self.staff_user.pk)

    def test_notify_comment_rejected_task_without_moderator(self):
        """Test rejection notification without moderator."""
        comment = self.create_comment(is_public=True)

        with patch('django_comments.notifications.notification_service') as mock_service:
            tasks.notify_comment_rejected_task(str(comment.pk), None)

            call_args = mock_service.notify_comment_rejected.call_args[0]
            self.assertIsNone(call_args[1])


# ============================================================================
# MODERATOR NOTIFICATION TASK TESTS
# ============================================================================

class NotifyModeratorsTaskTests(BaseCommentTestCase):
    """Test notify_moderators_task."""

    def setUp(self):
        super().setUp()
        if not TASKS_MODULE_AVAILABLE:
            self.skipTest("Tasks module not available")
        mail.outbox = []

    def test_notify_moderators_task_success(self):
        """Test successful moderator notification task."""
        comment = self.create_comment(
            user=self.regular_user,
            is_public=False
        )

        with patch('django_comments.notifications.notification_service') as mock_service:
            tasks.notify_moderators_task(str(comment.pk))

            mock_service.notify_moderators.assert_called_once_with(comment)

    def test_notify_moderators_task_comment_not_found(self):
        """Test task handles comment not found gracefully."""
        fake_uuid = str(uuid.uuid4())

        with self.assertLogs(comments_settings.LOGGER_NAME, level='ERROR') as logs:
            tasks.notify_moderators_task(fake_uuid)

        self.assertTrue(len(logs.output) > 0)


# ============================================================================
# FLAG NOTIFICATION TASK TESTS
# ============================================================================

class NotifyModeratorsOfFlagTaskTests(BaseCommentTestCase):
    """Test notify_moderators_of_flag_task."""

    def setUp(self):
        super().setUp()
        if not TASKS_MODULE_AVAILABLE:
            self.skipTest("Tasks module not available")
        mail.outbox = []

    def test_notify_moderators_of_flag_task_success(self):
        """Test successful flag notification task."""
        comment = self.create_comment(user=self.regular_user)

        flag = CommentFlag.objects.create(
            comment_type=ContentType.objects.get_for_model(self.Comment),
            comment_id=str(comment.pk),
            user=self.staff_user,
            flag='spam',
            reason='This is spam'
        )

        with patch('django_comments.notifications.notification_service') as mock_service:
            mock_service._get_moderator_emails.return_value = ['mod@example.com']
            mock_service._get_notification_context.return_value = {'site_name': 'Test'}

            tasks.notify_moderators_of_flag_task(str(comment.pk), str(flag.pk), 1)

            self.assertEqual(mock_service._send_notification_email.call_count, 1)

    def test_notify_moderators_of_flag_task_no_moderator_emails(self):
        """Test flag notification with no moderator emails configured."""
        comment = self.create_comment(user=self.regular_user)

        flag = CommentFlag.objects.create(
            comment_type=ContentType.objects.get_for_model(self.Comment),
            comment_id=str(comment.pk),
            user=self.staff_user,
            flag='spam'
        )

        with patch('django_comments.notifications.notification_service') as mock_service:
            mock_service._get_moderator_emails.return_value = []

            tasks.notify_moderators_of_flag_task(str(comment.pk), str(flag.pk), 1)

            mock_service._send_notification_email.assert_not_called()

    def test_notify_moderators_of_flag_task_comment_not_found(self):
        """Test task handles comment not found gracefully."""
        fake_comment_id = str(uuid.uuid4())
        fake_flag_id = str(uuid.uuid4())

        with self.assertLogs(comments_settings.LOGGER_NAME, level='ERROR') as logs:
            tasks.notify_moderators_of_flag_task(fake_comment_id, fake_flag_id, 1)

        self.assertTrue(len(logs.output) > 0)

    def test_notify_moderators_of_flag_task_with_multiple_flags(self):
        """Test flag notification includes flag count."""
        comment = self.create_comment(user=self.regular_user)

        flag1 = CommentFlag.objects.create(
            comment_type=ContentType.objects.get_for_model(self.Comment),
            comment_id=str(comment.pk),
            user=self.staff_user,
            flag='spam'
        )

        flag2 = CommentFlag.objects.create(
            comment_type=ContentType.objects.get_for_model(self.Comment),
            comment_id=str(comment.pk),
            user=self.regular_user,
            flag='offensive'
        )

        with patch('django_comments.notifications.notification_service') as mock_service:
            mock_service._get_moderator_emails.return_value = ['mod@example.com']
            mock_service._get_notification_context.return_value = {'site_name': 'Test'}

            tasks.notify_moderators_of_flag_task(str(comment.pk), str(flag1.pk), 2)

            call_args = mock_service._send_notification_email.call_args
            context = call_args[1]['context']
            self.assertEqual(context['flag_count'], 2)


# ============================================================================
# AUTO-HIDE NOTIFICATION TASK TESTS
# ============================================================================

class NotifyAutoHideTaskTests(BaseCommentTestCase):
    """Test notify_auto_hide_task."""

    def setUp(self):
        super().setUp()
        if not TASKS_MODULE_AVAILABLE:
            self.skipTest("Tasks module not available")
        mail.outbox = []

    def test_notify_auto_hide_task_success(self):
        """Test successful auto-hide notification task."""
        comment = self.create_comment(user=self.regular_user)

        with patch('django_comments.notifications.notification_service') as mock_service:
            mock_service._get_moderator_emails.return_value = ['mod@example.com']
            mock_service._get_notification_context.return_value = {'site_name': 'Test'}

            tasks.notify_auto_hide_task(str(comment.pk), 5)

            self.assertEqual(mock_service._send_notification_email.call_count, 1)
            call_args = mock_service._send_notification_email.call_args
            context = call_args[1]['context']
            self.assertEqual(context['flag_count'], 5)
            self.assertEqual(context['auto_action'], 'hidden')

    def test_notify_auto_hide_task_no_moderators(self):
        """Test auto-hide notification with no moderators."""
        comment = self.create_comment(user=self.regular_user)

        with patch('django_comments.notifications.notification_service') as mock_service:
            mock_service._get_moderator_emails.return_value = []

            tasks.notify_auto_hide_task(str(comment.pk), 5)

            mock_service._send_notification_email.assert_not_called()


# ============================================================================
# USER BAN NOTIFICATION TASK TESTS
# ============================================================================

class NotifyUserBannedTaskTests(BaseCommentTestCase):
    """Test notify_user_banned_task."""

    def setUp(self):
        super().setUp()
        if not TASKS_MODULE_AVAILABLE:
            self.skipTest("Tasks module not available")
        mail.outbox = []

    def test_notify_user_banned_task_success(self):
        """Test successful user ban notification task."""
        ban = BannedUser.objects.create(
            user=self.regular_user,
            reason='Spam',
            banned_by=self.staff_user
        )

        with patch('django_comments.notifications.notification_service') as mock_service:
            mock_service._get_notification_context.return_value = {'site_name': 'Test'}

            tasks.notify_user_banned_task(str(ban.pk))

            self.assertEqual(mock_service._send_notification_email.call_count, 1)

    def test_notify_user_banned_task_user_no_email(self):
        """Test ban notification skips users without email."""
        user_no_email = User.objects.create_user(
            username='noemail',
            email='',
            password='testpass123'
        )

        ban = BannedUser.objects.create(
            user=user_no_email,
            reason='Spam',
            banned_by=self.staff_user
        )

        with patch('django_comments.notifications.notification_service') as mock_service:
            tasks.notify_user_banned_task(str(ban.pk))

            mock_service._send_notification_email.assert_not_called()

    def test_notify_user_banned_task_temporary_ban(self):
        """Test notification for temporary ban."""
        banned_until = timezone.now() + timedelta(days=7)

        ban = BannedUser.objects.create(
            user=self.regular_user,
            reason='Inappropriate language',
            banned_by=self.staff_user,
            banned_until=banned_until
        )

        with patch('django_comments.notifications.notification_service') as mock_service:
            mock_service._get_notification_context.return_value = {'site_name': 'Test'}

            tasks.notify_user_banned_task(str(ban.pk))

            call_args = mock_service._send_notification_email.call_args
            subject = call_args[1]['subject']
            self.assertIn('until', str(subject))

    def test_notify_user_banned_task_permanent_ban(self):
        """Test notification for permanent ban."""
        ban = BannedUser.objects.create(
            user=self.regular_user,
            reason='Severe violations',
            banned_by=self.staff_user,
            banned_until=None
        )

        with patch('django_comments.notifications.notification_service') as mock_service:
            mock_service._get_notification_context.return_value = {'site_name': 'Test'}

            tasks.notify_user_banned_task(str(ban.pk))

            call_args = mock_service._send_notification_email.call_args
            subject = call_args[1]['subject']
            self.assertIn('permanently', str(subject))


# ============================================================================
# USER UNBAN NOTIFICATION TASK TESTS
# ============================================================================

class NotifyUserUnbannedTaskTests(BaseCommentTestCase):
    """Test notify_user_unbanned_task."""

    def setUp(self):
        super().setUp()
        if not TASKS_MODULE_AVAILABLE:
            self.skipTest("Tasks module not available")
        mail.outbox = []

    def test_notify_user_unbanned_task_success(self):
        """Test successful user unban notification task."""
        with patch('django_comments.notifications.notification_service') as mock_service:
            mock_service._get_notification_context.return_value = {'site_name': 'Test'}

            tasks.notify_user_unbanned_task(
                self.regular_user.pk,
                self.staff_user.pk,
                'Original spam violation'
            )

            self.assertEqual(mock_service._send_notification_email.call_count, 1)

            call_args = mock_service._send_notification_email.call_args
            context = call_args[1]['context']
            self.assertEqual(context['user'], self.regular_user)
            self.assertEqual(context['unbanned_by'].pk, self.staff_user.pk)
            self.assertEqual(context['original_ban_reason'], 'Original spam violation')

    def test_notify_user_unbanned_task_without_unbanner(self):
        """Test unban notification without unbanner (automatic unban)."""
        with patch('django_comments.notifications.notification_service') as mock_service:
            mock_service._get_notification_context.return_value = {'site_name': 'Test'}

            tasks.notify_user_unbanned_task(
                self.regular_user.pk,
                None,
                'Expired temporary ban'
            )

            call_args = mock_service._send_notification_email.call_args
            context = call_args[1]['context']
            self.assertIsNone(context['unbanned_by'])

    def test_notify_user_unbanned_task_user_no_email(self):
        """Test unban notification skips users without email."""
        user_no_email = User.objects.create_user(
            username='noemail',
            email='',
            password='testpass123'
        )

        with patch('django_comments.notifications.notification_service') as mock_service:
            tasks.notify_user_unbanned_task(
                user_no_email.pk,
                self.staff_user.pk,
                'Test ban'
            )

            mock_service._send_notification_email.assert_not_called()

    def test_notify_user_unbanned_task_user_not_found(self):
        """Test task handles user not found gracefully."""
        fake_user_id = 99999

        with self.assertLogs(comments_settings.LOGGER_NAME, level='ERROR') as logs:
            tasks.notify_user_unbanned_task(fake_user_id, self.staff_user.pk, 'Test')

        self.assertTrue(len(logs.output) > 0)


# ============================================================================
# EDGE CASES AND REAL-WORLD SCENARIOS
# ============================================================================

class TaskEdgeCasesTests(BaseCommentTestCase):
    """Test edge cases and real-world scenarios."""

    def setUp(self):
        super().setUp()
        if not TASKS_MODULE_AVAILABLE:
            self.skipTest("Tasks module not available")
        mail.outbox = []

    def test_task_with_unicode_content(self):
        """Test tasks handle Unicode content correctly."""
        comment = self.create_comment(
            content="测试内容 with emoji 😀 and symbols ©®™",
            user=self.regular_user
        )

        with patch('django_comments.notifications.notification_service') as mock_service:
            tasks.notify_new_comment_task(str(comment.pk))

            mock_service.notify_new_comment.assert_called_once()

    def test_task_with_very_long_reason(self):
        """Test ban notification with very long reason."""
        long_reason = "A" * 1000

        ban = BannedUser.objects.create(
            user=self.regular_user,
            reason=long_reason,
            banned_by=self.staff_user
        )

        with patch('django_comments.notifications.notification_service') as mock_service:
            mock_service._get_notification_context.return_value = {'site_name': 'Test'}

            tasks.notify_user_banned_task(str(ban.pk))

    def test_multiple_tasks_execute_correctly(self):
        """Test multiple tasks can execute correctly in sequence."""
        comments = [
            self.create_comment(content=f"Comment {i}")
            for i in range(5)
        ]

        with patch('django_comments.notifications.notification_service') as mock_service:
            for comment in comments:
                tasks.notify_new_comment_task(str(comment.pk))

            self.assertEqual(mock_service.notify_new_comment.call_count, 5)

    def test_task_with_deleted_parent_comment(self):
        """Test reply notification when parent is deleted logs an error gracefully."""
        parent = self.create_comment(content="Parent")
        reply = self.create_comment(content="Reply", parent=parent)

        parent_id = parent.pk
        parent.delete()

        with self.assertLogs(comments_settings.LOGGER_NAME, level='ERROR') as logs:
            tasks.notify_comment_reply_task(str(reply.pk), str(parent_id))

        self.assertTrue(len(logs.output) > 0)

    def test_task_logging_on_success(self):
        """Test tasks log success messages."""
        comment = self.create_comment(user=self.regular_user)

        with patch('django_comments.notifications.notification_service'):
            with self.assertLogs(comments_settings.LOGGER_NAME, level='INFO') as logs:
                tasks.notify_new_comment_task(str(comment.pk))

                self.assertTrue(any('Sent new comment notification' in log for log in logs.output))

    def test_task_logging_on_error(self):
        """Test tasks log error messages when comment is not found."""
        fake_uuid = str(uuid.uuid4())

        with self.assertLogs(comments_settings.LOGGER_NAME, level='ERROR') as logs:
            tasks.notify_new_comment_task(fake_uuid)

        self.assertTrue(any('not found' in log for log in logs.output))


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TaskIntegrationTests(BaseCommentTestCase):
    """Test task integration with notification service."""

    def setUp(self):
        super().setUp()
        if not TASKS_MODULE_AVAILABLE:
            self.skipTest("Tasks module not available")
        mail.outbox = []

    @override_settings(DJANGO_COMMENTS_CONFIG={'SEND_NOTIFICATIONS': True})
    def test_task_integrates_with_notification_service(self):
        """Test task properly integrates with real notification service."""
        comment = self.create_comment(
            content="Integration test",
            user=self.regular_user
        )

        # Call task — uses real notification service but email backend is locmem
        tasks.notify_new_comment_task(str(comment.pk))

    def test_task_chain_multiple_notifications(self):
        """Test chaining multiple notification tasks."""
        parent = self.create_comment(content="Parent", user=self.staff_user)
        reply = self.create_comment(content="Reply", parent=parent, user=self.regular_user)

        with patch('django_comments.notifications.notification_service') as mock_service:
            tasks.notify_new_comment_task(str(parent.pk))
            tasks.notify_comment_reply_task(str(reply.pk), str(parent.pk))

            self.assertEqual(mock_service.notify_new_comment.call_count, 1)
            self.assertEqual(mock_service.notify_comment_reply.call_count, 1)


# ============================================================================
# PERFORMANCE TESTS
# ============================================================================

class TaskPerformanceTests(BaseCommentTestCase):
    """Test task performance characteristics."""

    def setUp(self):
        super().setUp()
        if not TASKS_MODULE_AVAILABLE:
            self.skipTest("Tasks module not available")

    def test_task_completes_quickly(self):
        """Test task completes in reasonable time."""
        import time

        comment = self.create_comment(user=self.regular_user)

        with patch('django_comments.notifications.notification_service'):
            start = time.time()
            tasks.notify_new_comment_task(str(comment.pk))
            elapsed = time.time() - start

            self.assertLess(elapsed, 1.0)

    def test_bulk_task_execution(self):
        """Test executing many tasks in sequence."""
        comments = [
            self.create_comment(content=f"Bulk {i}")
            for i in range(50)
        ]

        with patch('django_comments.notifications.notification_service'):
            import time
            start = time.time()

            for comment in comments:
                tasks.notify_new_comment_task(str(comment.pk))

            elapsed = time.time() - start

            self.assertLess(elapsed, 5.0)
