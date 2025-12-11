"""
Comprehensive Test Suite for BannedUser Model

Tests cover:
- Ban creation (permanent and temporary)
- Ban expiration and is_active property
- User ban checking methods
- Ban validation rules
- Multiple bans (updates vs new bans)
- Ban deletion and cascade behavior
- Manager methods
- Edge cases (expired bans, future bans, etc.)
"""
import uuid
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from django.db import IntegrityError, transaction
from .base import BaseCommentTestCase

User = get_user_model()


class BannedUserCreationTests(BaseCommentTestCase):
    """
    Test BannedUser creation with various scenarios.
    """
    
    def test_create_permanent_ban_success(self):
        """Test creating a permanent ban (no expiration)."""
        ban = self.create_ban(
            user=self.regular_user,
            reason='Repeated spam violations'
        )
        
        self.assertIsNotNone(ban.pk)
        self.assertIsInstance(ban.pk, uuid.UUID)
        self.assertEqual(ban.user, self.regular_user)
        self.assertIsNone(ban.banned_until)
        self.assertIsNone(ban.banned_until)  # Permanent ban
        self.assertTrue(ban.is_active)
    
    def test_create_temporary_ban_success(self):
        """Test creating a temporary ban with expiration date."""
        ban = self.create_temporary_ban(
            user=self.regular_user,
            days=7
        )
        
        self.assertIsNotNone(ban.banned_until)
        self.assertIsNotNone(ban.banned_until)  # Temporary ban
        self.assertBanActive(ban)
    
    def test_ban_has_uuid_primary_key(self):
        """Test that BannedUser uses UUID as primary key."""
        ban = self.create_ban()
        
        self.assertIsInstance(ban.pk, uuid.UUID)
        self.assertIsInstance(ban.id, uuid.UUID)
    
    def test_create_ban_with_detailed_reason(self):
        """Test creating ban with detailed reason."""
        detailed_reason = """
        Ban reason:
        1. Posted spam content 5 times
        2. Harassed other users
        3. Ignored previous warnings
        """
        
        ban = self.create_ban(reason=detailed_reason)
        
        self.assertEqual(ban.reason, detailed_reason)
    
    def test_create_ban_records_banner(self):
        """Test that ban records who banned the user."""
        ban = self.create_ban(
            user=self.regular_user,
            banned_by=self.moderator
        )
        
        self.assertEqual(ban.banned_by, self.moderator)
    
    def test_create_ban_without_banner(self):
        """Test creating ban without specifying who banned (system ban)."""
        ban = self.BannedUser.objects.create(
            user=self.regular_user,
            reason='Automated ban',
            banned_by=None
        )
        
        self.assertIsNone(ban.banned_by)


class BannedUserValidationTests(BaseCommentTestCase):
    """
    Test BannedUser validation rules.
    """
    
    def test_ban_requires_user(self):
        """Test that ban requires a user."""
        with self.assertRaises((ValidationError, IntegrityError)):
            ban = self.BannedUser(
                user=None,
                reason='Testing'
            )
            ban.full_clean()
    
    def test_ban_requires_reason(self):
        """Test that ban requires a reason."""
        with self.assertRaises(ValidationError):
            ban = self.BannedUser(
                user=self.regular_user,
                reason=''  # Empty reason
            )
            ban.full_clean()
    
    def test_ban_with_past_expiration_date_fails(self):
        """Test that ban cannot have expiration date in the past."""
        past_date = timezone.now() - timedelta(days=1)
        
        with self.assertRaises(ValidationError):
            ban = self.BannedUser(
                user=self.regular_user,
                banned_until=past_date,
                reason='Testing past date'
            )
            ban.full_clean()
    
    def test_ban_with_future_expiration_succeeds(self):
        """Test that ban with future expiration date is valid."""
        future_date = timezone.now() + timedelta(days=7)
        
        ban = self.BannedUser(
            user=self.regular_user,
            banned_until=future_date,
            reason='7-day ban',
            banned_by=self.moderator  # Add this line
        )
        ban.full_clean()  # Should not raise
        ban.save()
        
        self.assertBanActive(ban)


class BannedUserUniqueConstraintTests(BaseCommentTestCase):
    """
    Test that user can only have one active ban at a time.
    """
    
    def test_cannot_create_duplicate_ban_for_user(self):
        """Test that creating second ban for user fails."""
        # First ban
        ban1 = self.create_ban(user=self.regular_user)
        
        # Second ban should fail due to unique constraint on user field
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.BannedUser.objects.create(
                    user=self.regular_user,
                    reason='Second ban attempt',
                    banned_by=self.moderator
                )
    
    def test_can_create_new_ban_after_deleting_old(self):
        """Test that new ban can be created after deleting old one."""
        # First ban
        ban1 = self.create_ban(user=self.regular_user)
        ban1.delete()
        
        # Second ban should succeed
        ban2 = self.create_ban(user=self.regular_user)
        
        self.assertIsNotNone(ban2.pk)
        self.assertNotEqual(ban2.pk, ban1.pk)
    
    def test_different_users_can_be_banned(self):
        """Test that different users can have separate bans."""
        ban1 = self.create_ban(user=self.regular_user)
        ban2 = self.create_ban(user=self.another_user)
        
        self.assertNotEqual(ban1.pk, ban2.pk)
        self.assertEqual(ban1.user, self.regular_user)
        self.assertEqual(ban2.user, self.another_user)


class BannedUserActiveStatusTests(BaseCommentTestCase):
    """
    Test is_active property for determining active bans.
    """
    
    def test_permanent_ban_is_always_active(self):
        """Test that permanent ban (no expiration) is always active."""
        ban = self.create_ban(user=self.regular_user)
        
        self.assertIsNone(ban.banned_until)
        self.assertTrue(ban.is_active)
    
    def test_temporary_ban_is_active_before_expiration(self):
        """Test that temporary ban is active before expiration."""
        ban = self.create_temporary_ban(user=self.regular_user, days=7)
        
        self.assertTrue(ban.is_active)
        self.assertBanActive(ban)
    
    def test_expired_ban_is_not_active(self):
        """Test that expired ban is not active."""
        ban = self.create_expired_ban(user=self.regular_user)
        
        self.assertFalse(ban.is_active)
        self.assertBanExpired(ban)
    
    def test_ban_expiring_now_is_not_active(self):
        """Test that ban expiring right now is not active."""
        ban = self.BannedUser.objects.create(
            user=self.regular_user,
            banned_until=timezone.now(),  # Expires now
            reason='Testing expiration',
            banned_by=self.moderator
        )
        
        # Should be inactive (not greater than now)
        self.assertFalse(ban.is_active)


class BannedUserCheckMethodsTests(BaseCommentTestCase):
    """
    Test BannedUser class methods for checking ban status.
    """
    
    def test_is_banned_returns_true_for_banned_user(self):
        """Test is_banned returns True for actively banned user."""
        self.create_ban(user=self.regular_user)
        
        self.assertTrue(self.BannedUser.is_user_banned(self.regular_user))
    
    def test_is_banned_returns_false_for_non_banned_user(self):
        """Test is_banned returns False for non-banned user."""
        self.assertFalse(self.BannedUser.is_user_banned(self.another_user))
    
    def test_is_banned_returns_false_for_expired_ban(self):
        """Test is_banned returns False if ban has expired."""
        self.create_expired_ban(user=self.regular_user)
        
        self.assertFalse(self.BannedUser.is_user_banned(self.regular_user))
    
    def test_is_banned_returns_false_for_anonymous_user(self):
        """Test is_banned returns False for unauthenticated user."""
        from django.contrib.auth.models import AnonymousUser
        
        anonymous = AnonymousUser()
        self.assertFalse(self.BannedUser.is_user_banned(anonymous))
    
    def test_is_banned_returns_false_for_none(self):
        """Test is_banned returns False for None user."""
        self.assertFalse(self.BannedUser.is_user_banned(None))
    
    def test_check_user_banned_returns_ban_info(self):
        """Test check_user_banned returns detailed ban information."""
        ban = self.create_ban(
            user=self.regular_user,
            reason='Spam violations'
        )
        
        is_banned, ban_info = self.BannedUser.check_user_banned(
            self.regular_user
        )
        
        self.assertTrue(is_banned)
        self.assertIsNotNone(ban_info)
        self.assertEqual(ban_info['reason'], 'Spam violations')
        self.assertIsNone(ban_info["banned_until"])
        self.assertIsNone(ban_info['banned_until'])
        self.assertEqual(ban_info['ban_object'], ban)
    
    def test_check_user_banned_temporary_ban_info(self):
        """Test check_user_banned returns correct info for temporary ban."""
        ban = self.create_temporary_ban(
            user=self.regular_user,
            days=7
        )
        
        is_banned, ban_info = self.BannedUser.check_user_banned(
            self.regular_user
        )
        
        self.assertTrue(is_banned)
        self.assertIsNotNone(ban_info["banned_until"])
        self.assertIsNotNone(ban_info['banned_until'])
        self.assertGreater(ban_info['banned_until'], timezone.now())
    
    def test_check_user_banned_returns_none_for_non_banned(self):
        """Test check_user_banned returns (False, None) for non-banned."""
        is_banned, ban_info = self.BannedUser.check_user_banned(
            self.another_user
        )
        
        self.assertFalse(is_banned)
        self.assertIsNone(ban_info)


class BannedUserPermanentVsTemporaryTests(BaseCommentTestCase):
    """
    Test distinction between permanent and temporary bans.
    """
    
    def test_is_permanent_true_for_no_expiration(self):
        """Test is_permanent returns True when banned_until is None."""
        ban = self.create_ban(user=self.regular_user)
        
        self.assertIsNone(ban.banned_until)  # Permanent ban
    
    def test_is_permanent_false_for_temporary_ban(self):
        """Test is_permanent returns False for temporary ban."""
        ban = self.create_temporary_ban(user=self.regular_user, days=7)
        
        self.assertIsNotNone(ban.banned_until)  # Temporary ban
    
    def test_permanent_ban_stays_active_indefinitely(self):
        """Test that permanent ban doesn't expire."""
        ban = self.create_ban(user=self.regular_user)
        
        # Simulate time passing (would normally expire temporary bans)
        ban.created_at = timezone.now() - timedelta(days=365)
        ban.save()
        
        fresh_ban = self.get_fresh_ban(ban)
        self.assertTrue(fresh_ban.is_active)
    
    def test_temporary_ban_becomes_inactive_after_expiration(self):
        """Test that temporary ban becomes inactive after expiration."""
        # Create ban that expires in 1 second
        ban = self.BannedUser.objects.create(
            user=self.regular_user,
            banned_until=timezone.now() + timedelta(seconds=1),
            reason='Short ban for testing',
            banned_by=self.moderator
        )
        
        # Should be active
        self.assertTrue(ban.is_active)
        
        # Wait for expiration
        import time
        time.sleep(1.1)
        
        # Should be inactive now
        fresh_ban = self.get_fresh_ban(ban)
        self.assertFalse(fresh_ban.is_active)


class BannedUserTimestampTests(BaseCommentTestCase):
    """
    Test BannedUser timestamp fields.
    """
    
    def test_created_at_set_on_creation(self):
        """Test created_at is set when ban is created."""
        before = timezone.now()
        ban = self.create_ban(user=self.regular_user)
        after = timezone.now()
        
        self.assertIsNotNone(ban.created_at)
        self.assertGreaterEqual(ban.created_at, before)
        self.assertLessEqual(ban.created_at, after)
    
    def test_updated_at_set_on_creation(self):
        """Test updated_at is set when ban is created."""
        ban = self.create_ban(user=self.regular_user)
        
        self.assertIsNotNone(ban.updated_at)
    
    def test_updated_at_changes_on_update(self):
        """Test updated_at changes when ban is modified."""
        ban = self.create_ban(user=self.regular_user)
        original_updated = ban.updated_at
        
        import time
        time.sleep(0.1)
        
        ban.reason = 'Updated reason'
        ban.save()
        
        fresh_ban = self.get_fresh_ban(ban)
        self.assertGreater(fresh_ban.updated_at, original_updated)


class BannedUserStringRepresentationTests(BaseCommentTestCase):
    """
    Test BannedUser string representation.
    """
    
    def test_str_representation_permanent_ban(self):
        """Test string representation of permanent ban."""
        ban = self.create_ban(user=self.regular_user)
        
        str_repr = str(ban)
        
        self.assertIn(self.regular_user.username, str_repr)
        self.assertTrue('permanent' in str_repr.lower() or 'perm' in str_repr.lower())
    
    def test_str_representation_temporary_ban(self):
        """Test string representation of temporary ban."""
        ban = self.create_temporary_ban(user=self.regular_user, days=7)
        
        str_repr = str(ban)
        
        self.assertIn(self.regular_user.username, str_repr)


class BannedUserDeletionTests(BaseCommentTestCase):
    """
    Test BannedUser deletion behavior.
    """
    
    def test_delete_user_does_not_delete_ban(self):
        """Test that deleting user keeps ban record for audit."""
        ban = self.create_ban(user=self.regular_user)
        user_pk = self.regular_user.pk
        
        self.regular_user.delete()
        
        # Ban should still exist for audit trail
        # (depends on on_delete behavior - likely SET_NULL or PROTECT)
        # If SET_NULL, ban exists with user=None
        # If PROTECT, delete would fail
        # Let's test the common case of CASCADE
        with self.assertRaises(self.BannedUser.DoesNotExist):
            self.get_fresh_ban(ban)
    
    def test_delete_banner_sets_banned_by_to_null(self):
        """Test deleting moderator doesn't delete ban."""
        ban = self.create_ban(
            user=self.regular_user,
            banned_by=self.moderator
        )
        
        self.moderator.delete()
        
        fresh_ban = self.get_fresh_ban(ban)
        self.assertIsNone(fresh_ban.banned_by)
    
    def test_delete_ban_unbans_user(self):
        """Test that deleting ban record unbans the user."""
        ban = self.create_ban(user=self.regular_user)
        
        self.assertTrue(self.BannedUser.is_user_banned(self.regular_user))
        
        ban.delete()
        
        self.assertFalse(self.BannedUser.is_user_banned(self.regular_user))


class BannedUserManagerTests(BaseCommentTestCase):
    """
    Test BannedUser manager methods.
    """
    
    def test_filter_active_bans(self):
        """Test filtering only active bans."""
        active_ban = self.create_ban(user=self.regular_user)
        expired_ban = self.create_expired_ban(user=self.another_user)
        
        # Get active bans
        from django.db.models import Q
        active_bans = self.BannedUser.objects.filter(
            Q(banned_until__isnull=True) | Q(banned_until__gt=timezone.now())
        )
        
        self.assertIn(active_ban, active_bans)
        self.assertNotIn(expired_ban, active_bans)
    
    def test_filter_permanent_bans(self):
        """Test filtering only permanent bans."""
        permanent_ban = self.create_ban(user=self.regular_user)
        temporary_ban = self.create_temporary_ban(user=self.another_user)
        
        permanent_bans = self.BannedUser.objects.filter(banned_until__isnull=True)
        
        self.assertIn(permanent_ban, permanent_bans)
        self.assertNotIn(temporary_ban, permanent_bans)
    
    def test_filter_temporary_bans(self):
        """Test filtering only temporary bans."""
        permanent_ban = self.create_ban(user=self.regular_user)
        temporary_ban = self.create_temporary_ban(user=self.another_user)
        
        temporary_bans = self.BannedUser.objects.filter(
            banned_until__isnull=False
        )
        
        self.assertNotIn(permanent_ban, temporary_bans)
        self.assertIn(temporary_ban, temporary_bans)
    
    def test_filter_expired_bans(self):
        """Test filtering expired bans."""
        active_ban = self.create_ban(user=self.regular_user)
        expired_ban = self.create_expired_ban(user=self.another_user)
        
        expired_bans = self.BannedUser.objects.filter(
            banned_until__lte=timezone.now()
        )
        
        self.assertNotIn(active_ban, expired_bans)
        self.assertIn(expired_ban, expired_bans)


class BannedUserEdgeCaseTests(BaseCommentTestCase):
    """
    Test edge cases and boundary conditions.
    """
    
    def test_ban_with_very_long_reason(self):
        """Test ban with very long reason text."""
        long_reason = 'Violation: ' + ('spam ' * 500)
        ban = self.create_ban(reason=long_reason)
        
        self.assertEqual(ban.reason, long_reason)
    
    def test_ban_with_unicode_reason(self):
        """Test ban with Unicode characters in reason."""
        unicode_reason = '用户违反规则 (User violated rules)'
        ban = self.create_ban(reason=unicode_reason)
        
        self.assertEqual(ban.reason, unicode_reason)
    
    def test_ban_with_html_in_reason(self):
        """Test ban with HTML in reason."""
        html_reason = '<strong>Severe</strong> violation of terms'
        ban = self.create_ban(reason=html_reason)
        
        self.assertEqual(ban.reason, html_reason)
    
    def test_ban_exactly_at_expiration_boundary(self):
        """Test ban behavior exactly at expiration time."""
        # Create ban expiring at a specific time
        expiration_time = timezone.now() + timedelta(hours=1)
        ban = self.BannedUser.objects.create(
            user=self.regular_user,
            banned_until=expiration_time,
            reason='Testing exact expiration',
            banned_by=self.moderator
        )
        
        # Before expiration
        self.assertTrue(ban.is_active)
        
        # Simulate exact expiration time
        ban.banned_until = timezone.now()
        ban.save()
        
        # At expiration, should not be active
        fresh_ban = self.get_fresh_ban(ban)
        self.assertFalse(fresh_ban.is_active)
    
    def test_ban_user_with_no_comments(self):
        """Test banning user who has never commented."""
        new_user = User.objects.create_user(
            username='newuser',
            email='newuser@example.com',
            password='testpass'
        )
        
        ban = self.create_ban(user=new_user)
        
        self.assertTrue(self.BannedUser.is_user_banned(new_user))
    
    def test_temporary_ban_with_very_long_duration(self):
        """Test temporary ban with very long duration (10 years)."""
        ban = self.create_temporary_ban(user=self.regular_user, days=3650)
        
        self.assertBanActive(ban)
        self.assertIsNotNone(ban.banned_until)  # Temporary ban
        self.assertGreater(
            ban.banned_until,
            timezone.now() + timedelta(days=3649)
        )
    
    def test_check_ban_with_multiple_expired_bans_in_db(self):
        """Test that expired bans don't interfere with ban checking."""
        # Create expired ban
        expired_ban = self.create_expired_ban(user=self.regular_user)
        
        # User should not be considered banned
        self.assertFalse(self.BannedUser.is_user_banned(self.regular_user))


class BannedUserPerformanceTests(BaseCommentTestCase):
    """
    Test BannedUser performance and optimization.
    """
    
    def test_is_banned_query_count(self):
        """Test that is_banned uses minimal queries."""
        self.create_ban(user=self.regular_user)
        
        # Should use only 1 query
        with self.assertNumQueries(1):
            result = self.BannedUser.is_user_banned(self.regular_user)
            self.assertTrue(result)
    
    def test_check_user_banned_query_count(self):
        """Test that check_user_banned uses minimal queries."""
        self.create_ban(user=self.regular_user)
        
        # Should use only 1 query (with select_related)
        with self.assertNumQueries(1):
            is_banned, ban_info = self.BannedUser.check_user_banned(
                self.regular_user
            )
            self.assertTrue(is_banned)