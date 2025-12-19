from typing import Dict, Any, Optional
from django.contrib.contenttypes.models import ContentType
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from ..conf import comments_settings
from ..models import CommentFlag, BannedUser, CommentRevision, ModerationAction, Comment
from ..utils import (
    get_comment_model,
    get_model_from_content_type_string,
    is_comment_content_allowed,
    process_comment_content,
    apply_automatic_flags,
    log_moderation_action,
    get_or_create_system_user,
    process_comment_content,
)
from ..formatting import render_comment_content 
from django.contrib.auth import get_user_model
import re

Comment = get_comment_model()
User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for the User model, used within CommentSerializer.
    Includes role information for frontend badge display.
    """
    display_name = serializers.SerializerMethodField()
    is_moderator = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'id', 'username', 'email', 'display_name',
            'is_staff', 'is_superuser', 'is_moderator'
        )
        read_only_fields = fields

    def get_display_name(self, obj) -> str:
        return obj.get_full_name() or obj.get_username()
    
    def get_is_moderator(self, obj) -> bool:
        """
        Check if user has moderator permissions.
        Returns True if user has can_moderate_comments permission.
        """
        return obj.has_perm('django_comments.can_moderate_comments')


class ContentTypeSerializer(serializers.ModelSerializer):
    """
    Serializer for ContentType model.
    """
    app_label = serializers.CharField(read_only=True)
    model = serializers.CharField(read_only=True)
    
    class Meta:
        model = ContentType
        fields = ('id', 'app_label', 'model')


class CommentFlagSerializer(serializers.ModelSerializer):
    """
    serializer for comment flags with review status.
    """
    flag_type = serializers.ChoiceField(
        source='flag',
        choices=CommentFlag.FLAG_CHOICES
    )
    reviewed_by_info = UserSerializer(source='reviewed_by', read_only=True)
    user_info = UserSerializer(source='user', read_only=True)
    flag_display = serializers.CharField(source='get_flag_display', read_only=True)
    review_action_display = serializers.CharField(source='get_review_action_display', read_only=True)
    
    class Meta:
        model = CommentFlag
        fields = (
            'id', 'flag_type', 'flag_display', 'reason', 'created_at',
            'user', 'user_info',
            'reviewed', 'reviewed_by', 'reviewed_by_info', 'reviewed_at',
            'review_action', 'review_action_display', 'review_notes'
        )
        read_only_fields = (
            'id', 'created_at', 'reviewed', 'reviewed_by', 'reviewed_at',
            'review_action', 'flag_display', 'review_action_display'
        )


class CreateCommentFlagSerializer(serializers.ModelSerializer):
    """
    Serializer for creating comment flags.
    """
    flag_type = serializers.ChoiceField(
        source='flag',
        choices=CommentFlag.FLAG_CHOICES
    )
    
    class Meta:
        model = CommentFlag
        fields = ('flag_type', 'reason')
    
    def create(self, validated_data):
        # Get comment and user from context
        comment = self.context.get('comment')
        user = self.context.get('request').user
        
        # Create or update the flag
        flag_type = validated_data.get('flag', 'other')
        reason = validated_data.get('reason', '')
        
        try:
            
            flag, created = CommentFlag.objects.create_or_get_flag(
                comment=comment,
                user=user,
                flag=flag_type,
                reason=reason
            )
            return flag
        except Exception as e:
            raise serializers.ValidationError(str(e))


class RecursiveCommentSerializer(serializers.Serializer):
    """
    Serializer for handling children comments recursively with depth limiting.
    """
    def to_representation(self, value):
        # Get max recursion depth from context or use default
        max_depth = self.context.get('max_recursion_depth', 3)
        current_depth = self.context.get('current_depth', 0)
        
        # If we've reached max depth, don't recurse further
        if current_depth >= max_depth:
            # Return minimal representation
            return {
                'id': str(value.pk),
                'content': value.content[:100] + '...' if len(value.content) > 100 else value.content,
                'has_children': value.children.exists() if hasattr(value, 'children') else False,
                'depth_limit_reached': True
            }
        
        # Create context with incremented depth
        context = self.context.copy()
        context['current_depth'] = current_depth + 1
        
        serializer = CommentSerializer(value, context=context)
        return serializer.data


class CommentSerializer(serializers.ModelSerializer):
    """
    FIXED & COMPLETE: Serializer for Comment model with proper flag counting.
    
    This serializer includes ALL methods from the original implementation
    with fixes for UUID handling in flag counts and related methods.
    """
    
    # Write-only fields for creation
    content_type = serializers.CharField(
        write_only=True,
        required=False,  
        help_text=_("Content type in the format 'app_label.model_name'")
    )
    object_id = serializers.CharField(
        write_only=True,
        required=False, 
        help_text=_("ID of the object to comment on")
    )
    
    # Read-only info fields
    content_object_info = serializers.SerializerMethodField()
    
    # User fields
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())
    user_name = serializers.CharField(required=False, allow_blank=True)
    user_email = serializers.EmailField(required=False, allow_blank=True)
    user_info = serializers.SerializerMethodField()
    
    # Parent/threading fields
    parent = serializers.PrimaryKeyRelatedField(
        queryset=Comment.objects.all(),
        required=False,
        allow_null=True
    )
    children = serializers.SerializerMethodField()
    depth = serializers.IntegerField(read_only=True)
    
    # Content fields
    formatted_content = serializers.SerializerMethodField()
    
    # FIXED: Count fields with proper UUID handling
    flags_count = serializers.SerializerMethodField()  # CHANGED from IntegerField
    children_count = serializers.IntegerField(
        source='children_count_annotated',
        read_only=True,
        default=0
    )
    
    # Status fields
    is_flagged = serializers.SerializerMethodField()
    revisions_count = serializers.SerializerMethodField()
    moderation_actions_count = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = (
            'id', 'content', 'formatted_content', 'content_type', 'object_id', 'content_object_info',  
            'user', 'user_info', 'user_name', 'user_email',
            'parent', 'children', 'depth', 'thread_id', 'children_count',
            'created_at', 'updated_at', 'is_public', 'is_removed',
            'flags_count', 'is_flagged', 'revisions_count',
            'moderation_actions_count',
        )
        read_only_fields = (
            'id', 'formatted_content', 'content_object_info', 'user_info', 'children', 'thread_id',  
            'depth', 'created_at', 'updated_at', 'is_flagged', 'children_count',
            'revisions_count', 'moderation_actions_count',
            'is_public', 'is_removed', 
        )
    
    def to_representation(self, instance):
        """
        Customize representation to conditionally include fields.
        
        Excludes user_name and user_email for authenticated users since
        they have user_info instead.
        """
        representation = super().to_representation(instance)
        
        # Hide user_name and user_email for authenticated users
        if instance.user:
            representation.pop('user_name', None)
            representation.pop('user_email', None)
        
        return representation

    def get_formatted_content(self, obj) -> str:
        """
        Return formatted comment content based on COMMENT_FORMAT setting.
        
        Uses the formatting module to render content as:
        - Plain text (HTML escaped)
        - Markdown (if markdown installed)
        - HTML (sanitized)
        """
        try:
            return render_comment_content(obj.content)
        except Exception as e:
            # Fallback to raw content if formatting fails
            import logging
            logger = logging.getLogger(comments_settings.LOGGER_NAME)
            logger.error(f"Failed to format comment {obj.pk}: {e}")
            return obj.content

    def get_content_object_info(self, obj):
        """
        Get information about the commented object.
        
        FIXED: Always returns content_type and object_id info, even if the
        actual object has been deleted (content_object is None).
        """
        # Always return at minimum the content_type and object_id
        info = {
            'content_type': f"{obj.content_type.app_label}.{obj.content_type.model}",
            'object_id': str(obj.object_id),
        }
        
        # Try to get the actual object representation
        try:
            if obj.content_object:
                info['object_repr'] = str(obj.content_object)
                info['exists'] = True
            else:
                info['object_repr'] = '(deleted)'
                info['exists'] = False
        except Exception:
            # If there's any error accessing content_object
            info['object_repr'] = '(unavailable)'
            info['exists'] = False
        
        return info
    
    def get_user_info(self, obj):
        """
        Get user information using UserSerializer.
        
        NOTE: Make sure you have UserSerializer defined in your serializers.py
        """
        if not obj.user:
            return None
        
        # Import UserSerializer (should be defined in same file)
        from django_comments.api.serializers import UserSerializer
        return UserSerializer(obj.user).data
    
    def get_children(self, obj):
        """
        Get nested children comments using RecursiveCommentSerializer.
        
        NOTE: Make sure you have RecursiveCommentSerializer defined in your serializers.py
        """
        if hasattr(obj, 'children'):
            children = obj.children.all()
            if children:
                # Import RecursiveCommentSerializer (should be defined in same file)
                from django_comments.api.serializers import RecursiveCommentSerializer
                return RecursiveCommentSerializer(
                    children, 
                    many=True, 
                    context=self.context
                ).data
        return []
    
    def get_flags_count(self, obj) -> int:
        """
        FIXED: Get flag count with proper UUID handling and fallback.
        
        Tries to use the annotated value from optimized_for_list(),
        falls back to direct query with proper UUID conversion if not available.
        """
        # Try annotated value first (from optimized_for_list())
        if hasattr(obj, 'flags_count_annotated'):
            count = obj.flags_count_annotated
            # Handle None from Subquery
            return count if count is not None else 0
        
        # Fallback: Direct query with proper UUID handling
        comment_ct = ContentType.objects.get_for_model(Comment)
        count = CommentFlag.objects.filter(
            comment_type=comment_ct,
            comment_id=str(obj.pk)  # CRITICAL: Convert UUID to string
        ).count()
        
        return count
    
    def get_is_flagged(self, obj) -> bool:
        """
        FIXED: Check if comment has been flagged with proper UUID handling.
        """
        # Try annotated value first
        if hasattr(obj, 'flags_count_annotated'):
            count = obj.flags_count_annotated
            return count is not None and count > 0
        
        # Fallback: Check with proper UUID conversion
        comment_ct = ContentType.objects.get_for_model(Comment)
        return CommentFlag.objects.filter(
            comment_type=comment_ct,
            comment_id=str(obj.pk)  # CRITICAL: Convert UUID to string
        ).exists()

    def get_revisions_count(self, obj) -> int:
        """
        FIXED: Get count of comment revisions with proper UUID handling.
        """
        # Try annotated value first (if it exists)
        if hasattr(obj, 'revisions_count_annotated'):
            return getattr(obj, 'revisions_count_annotated', 0)
        
        # Fallback: Direct query
        return CommentRevision.objects.filter(
            comment_type=obj.content_type,
            comment_id=str(obj.pk)  # CRITICAL: Convert UUID to string
        ).count()

    def get_moderation_actions_count(self, obj) -> int:
        """
        FIXED: Get count of moderation actions with proper UUID handling.
        """
        # Try annotated value first (if it exists)
        if hasattr(obj, 'moderation_actions_count_annotated'):
            return getattr(obj, 'moderation_actions_count_annotated', 0)
        
        # Fallback: Direct query
        return ModerationAction.objects.filter(
            comment_type=obj.content_type,
            comment_id=str(obj.pk)  # CRITICAL: Convert UUID to string
        ).count()
    
    def validate_parent(self, value):
        """
        Validate that the parent comment exists and is for the same object.
        Also checks thread depth limits.
        """
        if not value:
            return value
            
        # Check if parent is for the same object
        content_type = self.initial_data.get('content_type')
        object_id = self.initial_data.get('object_id')
        
        if content_type and object_id:
            content_type_obj = ContentType.objects.get_for_model(
                get_model_from_content_type_string(content_type)
            )
            
            if (value.content_type != content_type_obj or 
                str(value.object_id) != str(object_id)):
                raise serializers.ValidationError(
                    _("Parent comment must be for the same object")
                )
        
        # Check thread depth limits
        max_depth = comments_settings.MAX_COMMENT_DEPTH
        if max_depth is not None and value.depth >= max_depth:
            raise serializers.ValidationError(
                _("Maximum thread depth of {max_depth} exceeded.").format(max_depth=max_depth)
            )
            
        return value
    
    def validate_content(self, value):
        """
        Validate that the comment content is allowed.
        Checks max length and content filtering (spam/profanity).
        """
        # Check max length first
        if len(value) > comments_settings.MAX_COMMENT_LENGTH:
            raise serializers.ValidationError(
                _("Comment content exceeds maximum length of {max_length} characters.").format(
                    max_length=comments_settings.MAX_COMMENT_LENGTH
                )
            )
        
        # Check if content is allowed (spam/profanity detection)
        is_allowed, reason = is_comment_content_allowed(value)
        if not is_allowed:
            raise serializers.ValidationError(
                _("Comment content is not allowed: {reason}").format(reason=reason)
            )
        
        return value
    
    def validate_object_id(self, value):
        """
        Convert object_id to string.
        The CharField handles both integer and UUID PKs automatically.
        """
        return str(value)
    
    def validate_content_type(self, value):
        """
        Validate that the content type is allowed.
        Checks if the model is in the list of commentable models.
        """
        try:
            model = get_model_from_content_type_string(value)
            if not model:
                raise serializers.ValidationError(
                    _("Invalid content type format. Use 'app_label.model_name'")
                )
                
            # Check if model is in the list of commentable models
            commentable_models = comments_settings.COMMENTABLE_MODELS
            if commentable_models and value.lower() not in [m.lower() for m in commentable_models]:
                raise serializers.ValidationError(
                    _("Comments are not enabled for this content type")
                )
                            
            return value
        except Exception as e:
            raise serializers.ValidationError(str(e))
    
    def validate(self, data):
        """
        Validate the comment data.
        
        SECURITY & MODERATION HANDLING:
        This method orchestrates the validation flow:
        1. Get request and user from context
        2. Skip validation for partial updates
        3. Clean security-sensitive fields (is_public, is_removed)
        4. Determine moderation status for new comments
        5. Validate content
        6. Handle anonymous vs authenticated comments
        7. Check if user is banned
        8. Validate required fields for creation
        """
        # Get the request from context
        request = self.context.get('request')
        if not request:
            raise serializers.ValidationError("Request context is required")
        
        user = request.user
        
        # For partial updates (PATCH), skip most validation
        if self.partial:
            return data
        
        # =====================================================================
        # SECURITY: Remove user-provided is_public and is_removed
        # These fields must be server-controlled, not user-controlled
        # =====================================================================
        data.pop('is_public', None)
        data.pop('is_removed', None)
        
        # =====================================================================
        # MODERATION: Determine is_public for NEW comments only
        # =====================================================================
        if not self.instance:  # Creating new comment
            from django_comments.utils import should_auto_approve_user
            
            if comments_settings.MODERATOR_REQUIRED:
                # Check if user should bypass moderation
                if should_auto_approve_user(user):
                    data['is_public'] = True
                else:
                    data['is_public'] = False
            else:
                # No moderation required - all comments are public by default
                data['is_public'] = True
            
            # Always False for new comments (only moderators can set this)
            data['is_removed'] = False
        
        # =====================================================================
        # CONTENT VALIDATION
        # =====================================================================
        # Ensure we have content
        content = data.get('content', '').strip()
        if not content:
            raise serializers.ValidationError({
                'content': _("Comment content cannot be empty")
            })
        
        # =====================================================================
        # ANONYMOUS vs AUTHENTICATED USER HANDLING
        # =====================================================================
        # For authenticated users, clear anonymous fields
        if user.is_authenticated:
            data.pop('user_name', None)
            data.pop('user_email', None)
        else:
            # For anonymous users, require either name or email
            user_name = data.get('user_name', '').strip()
            user_email = data.get('user_email', '').strip()
            
            if not user_name and not user_email:
                raise serializers.ValidationError({
                    'user_name': _("Anonymous comments must provide either a name or email")
                })
        
        # =====================================================================
        # BAN CHECKING
        # =====================================================================
        # Check if user is banned
        if user.is_authenticated:
            from django_comments.models import BannedUser
            if BannedUser.is_user_banned(user):
                raise serializers.ValidationError(
                    _("You are currently banned from commenting")
                )
        
        # =====================================================================
        # REQUIRED FIELDS FOR CREATION
        # =====================================================================
        # Validate that content_type and object_id are provided for creation
        if not self.instance:  # Creating new comment
            if 'content_type' not in data:
                raise serializers.ValidationError({
                    'content_type': _("This field is required for creating comments")
                })
            if 'object_id' not in data:
                raise serializers.ValidationError({
                    'object_id': _("This field is required for creating comments")
                })
        
        return data
    
    def create(self, validated_data):
        """
        FIXED: Create a new comment with content processing.
        
        NEW BEHAVIOR:
        - Processes content for spam/profanity
        - If 'hide' action: saves with is_public=False and logs moderation
        - If 'flag' action: saves normally and auto-flags
        - If 'delete' action: rejected in validation (never reaches here)
        
        Args:
            validated_data: Validated comment data
        
        Returns:
            Comment: Created comment instance
        """
        
        
        # Extract content_type and object_id
        content_type_str = validated_data.pop('content_type')
        object_id = validated_data.pop('object_id')
        
        # Get the content type and object
        model = get_model_from_content_type_string(content_type_str)
        content_type = ContentType.objects.get_for_model(model)
        
        # Process content for spam/profanity
        original_content = validated_data['content']
        processed_content, flags_to_apply = process_comment_content(original_content)
        
        # Update content if it was processed (e.g., profanity censored)
        if processed_content != original_content:
            validated_data['content'] = processed_content
        
        # =========================================================================
        # NEW: Handle 'hide' action - set is_public=False
        # =========================================================================
        if flags_to_apply.get('should_hide'):
            validated_data['is_public'] = False
        
        # Create the comment
        comment = Comment.objects.create(
            content_type=content_type,
            object_id=object_id,
            **validated_data
        )
        
        # =========================================================================
        # NEW: Log moderation action for auto-hidden comments
        # =========================================================================
        if flags_to_apply.get('should_hide'):
            system_user = get_or_create_system_user()
            hide_reason = flags_to_apply.get('hide_reason', 'Auto-hidden by system')
            
            log_moderation_action(
                comment=comment,
                moderator=system_user,
                action='rejected',  # Use 'rejected' action for hidden comments
                reason=hide_reason
            )
        
        # =========================================================================
        # Apply automatic flags if needed
        # =========================================================================
        if flags_to_apply.get('auto_flag_spam') or flags_to_apply.get('auto_flag_profanity'):
            apply_automatic_flags(comment)
        
        return comment

    
    def update(self, instance, validated_data):
        """
        Update a comment.
        
        The following fields are immutable and cannot be changed:
        - content_type: The type of object being commented on
        - object_id: The ID of the object being commented on
        - parent: The parent comment (for threading structure)
        - thread_id: The thread identifier
        - path: The materialized path for tree structure
        - is_public: Can only be changed via approve/reject endpoints
        - is_removed: Can only be changed via moderator actions
        """
        # Remove immutable fields that should never be updated
        immutable_fields = [
            'content_type', 'object_id', 'parent', 'thread_id', 'path',
            'is_public', 'is_removed'  
        ]
        for field in immutable_fields:
            validated_data.pop(field, None)
        
        # If content is being updated, process it for profanity
        if 'content' in validated_data:
            original_content = validated_data['content']
            processed_content, _ = process_comment_content(original_content)
            validated_data['content'] = processed_content
        
        # Use the default update behavior for remaining fields
        return super().update(instance, validated_data)

class BannedUserSerializer(serializers.ModelSerializer):
    """
    Serializer for BannedUser model.
    """
    user_info = UserSerializer(source='user', read_only=True)
    banned_by_info = UserSerializer(source='banned_by', read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    is_permanent = serializers.SerializerMethodField()
    
    class Meta:
        model = BannedUser
        fields = (
            'id', 'user', 'user_info', 'banned_until', 'reason',
            'banned_by', 'banned_by_info', 'created_at', 'updated_at',
            'is_active', 'is_permanent'
        )
        read_only_fields = ('id', 'created_at', 'updated_at', 'is_active')
    
    def get_is_permanent(self, obj) -> bool:
        """Check if ban is permanent (no expiration date)."""
        return obj.banned_until is None


class CommentRevisionSerializer(serializers.ModelSerializer):
    """
    Serializer for CommentRevision model.
    """
    edited_by_info = UserSerializer(source='edited_by', read_only=True)
    
    class Meta:
        model = CommentRevision
        fields = (
            'id', 'content', 'edited_by', 'edited_by_info',
            'edited_at', 'was_public', 'was_removed'
        )
        read_only_fields = fields


class ModerationActionSerializer(serializers.ModelSerializer):
    """
    Serializer for ModerationAction model.
    """
    moderator_info = UserSerializer(source='moderator', read_only=True)
    affected_user_info = UserSerializer(source='affected_user', read_only=True)
    action_display = serializers.CharField(source='get_action_display', read_only=True)
    
    class Meta:
        model = ModerationAction
        fields = (
            'id', 'comment_type', 'comment_id', 'moderator', 'moderator_info',
            'action', 'action_display', 'reason', 'affected_user', 'affected_user_info',
            'timestamp', 'ip_address'
        )
        read_only_fields = fields