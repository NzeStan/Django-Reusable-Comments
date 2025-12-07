from typing import Dict, Any, Optional
from django.contrib.contenttypes.models import ContentType
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from ..conf import comments_settings
from ..models import CommentFlag, BannedUser, CommentRevision, ModerationAction
from ..utils import (
    get_comment_model,
    get_model_from_content_type_string,
    is_comment_content_allowed,
    process_comment_content,
    apply_automatic_flags,
)
from django.contrib.auth import get_user_model


Comment = get_comment_model()
User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for the User model, used within CommentSerializer.
    """
    display_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'username', 'display_name')
        read_only_fields = fields

    def get_display_name(self, obj) -> str:
        return obj.get_full_name() or obj.get_username()


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
            flag, created = CommentFlag.objects.update_or_create(
                comment=comment,
                user=user,
                flag=flag_type,
                defaults={'reason': reason}
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
    Serializer for comments with support for nested comments.
    """

    content_type = serializers.CharField(
        write_only=True,
        required=False,  # Not required for updates
        help_text=_("Content type in the format 'app_label.model_name'")
    )
    object_id = serializers.CharField(
        write_only=True,
        required=False,  # Not required for updates
        help_text=_("ID of the object to comment on")
    )
    content_object_info = serializers.SerializerMethodField()

    user = serializers.HiddenField(default=serializers.CurrentUserDefault())
    user_name = serializers.CharField(required=False, allow_blank=True)
    user_email = serializers.EmailField(required=False, allow_blank=True)
    user_url = serializers.URLField(required=False, allow_blank=True)
    user_info = UserSerializer(source='user', read_only=True)

    parent = serializers.PrimaryKeyRelatedField(
        queryset=Comment.objects.all(),
        required=False,
        allow_null=True
    )

    children = RecursiveCommentSerializer(many=True, read_only=True)
    depth = serializers.IntegerField(read_only=True)

    flags_count = serializers.IntegerField(
        source='flags_count_annotated',
        read_only=True,
        default=0
    )
    children_count = serializers.IntegerField(
        source='children_count_annotated',
        read_only=True,
        default=0
    )
    is_flagged = serializers.SerializerMethodField()
    revisions_count = serializers.SerializerMethodField()
    moderation_actions_count = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = (
            'id', 'content', 'content_type', 'object_id', 'content_object_info', 
            'user', 'user_info', 'user_name', 'user_email', 'user_url',
            'parent', 'children', 'depth', 'thread_id', 'children_count',
            'created_at', 'updated_at', 'is_public', 'is_removed',
            'flags_count', 'is_flagged', 'revisions_count',
            'moderation_actions_count',
        )
        read_only_fields = (
            'id', 'content_object_info', 'user_info', 'children', 'thread_id',
            'depth', 'created_at', 'updated_at', 'is_flagged', 'children_count',
            'revisions_count', 'moderation_actions_count',
        )

    def get_revisions_count(self, obj):
        """Get count of revisions for this comment."""
        from django.contrib.contenttypes.models import ContentType
        return CommentRevision.objects.filter(
            comment_type=ContentType.objects.get_for_model(obj),
            comment_id=str(obj.pk)
        ).count()
    
    def get_moderation_actions_count(self, obj):
        """Get count of moderation actions for this comment."""
        from django.contrib.contenttypes.models import ContentType
        return ModerationAction.objects.filter(
            comment_type=ContentType.objects.get_for_model(obj),
            comment_id=str(obj.pk)
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
        Validate object_id format if needed.
        """
        # Convert to string if it's an integer
        if isinstance(value, int):
            value = str(value)
        
        # If you want to ensure it's a valid UUID when USE_UUIDS is True
        if comments_settings.USE_UUIDS:
            import uuid
            try:
                # Now value is guaranteed to be a string
                uuid.UUID(value)
            except (ValueError, AttributeError) as e:
                raise serializers.ValidationError(
                    f"Invalid UUID format: {str(e)}"
                )
        return value
    
    def validate_content_type(self, value):
        """
        Validate that the content type is allowed.
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
        - Enforce anonymous rules.
        - Autofill user data for authenticated users.
        - Apply moderation settings.
        - Check bans and auto-approval.
        """
        if self.partial and 'user' not in data:
            return data

        request = self.context.get("request")
        user = data.get("user")

        # If explicitly passed or auto-filled by CurrentUserDefault
        if user and not getattr(user, "is_authenticated", False):
            data["user"] = None
            user = None  # reflect the change locally

        is_anonymous = not user

        if is_anonymous:
            if not comments_settings.ALLOW_ANONYMOUS:
                raise serializers.ValidationError(
                    {"detail": _("Anonymous comments are not allowed.")}
                )

            if not data.get("user_name"):
                data["user_name"] = _("Anonymous")

            if not data.get("user_email"):
                raise serializers.ValidationError(
                    {"user_email": _("Email is required for anonymous users.")}
                )

        else:
            # Authenticated: autofill from request.user
            data["user_name"] = user.get_full_name() or user.get_username()
            data["user_email"] = user.email
            data["user_url"] = self.get_user_url(user)

        # -----------------------------------------
        # 🚫 Check if user is banned
        # -----------------------------------------
        user_is_authenticated = bool(user and getattr(user, "is_authenticated", False))
        if user_is_authenticated:
            from ..utils import check_user_banned
            is_banned, ban_info = check_user_banned(user)

            if is_banned:
                if ban_info.get("is_permanent"):
                    raise serializers.ValidationError({
                        "detail": _(
                            "You are permanently banned from commenting. Reason: {reason}"
                        ).format(reason=ban_info.get("reason", _("No reason provided")))
                    })
                else:
                    banned_until = ban_info.get("banned_until")
                    until_str = banned_until.strftime("%Y-%m-%d") if banned_until else _("an unknown date")

                    raise serializers.ValidationError({
                        "detail": _(
                            "You are banned from commenting until {until}. Reason: {reason}"
                        ).format(
                            until=until_str,
                            reason=ban_info.get("reason", _("No reason provided"))
                        )
                    })

        # -----------------------------------------
        # ⭐ Auto-approve certain trusted users
        # -----------------------------------------
        if user_is_authenticated and not self.instance:
            from ..utils import should_auto_approve_user
            if should_auto_approve_user(user):
                data["is_public"] = True  # Override moderation requirement

        # -----------------------------------------
        # 🔒 Apply moderation for new comments
        # -----------------------------------------
        if not self.instance and comments_settings.MODERATOR_REQUIRED and "is_public" not in data:
            data["is_public"] = False

        return data


    def get_user_url(self, user):
        """
        Hook to allow host project to define how user_url is derived.
        Override or extend this in your project.
        """
        return getattr(user, "url", "")

    def get_content_object_info(self, obj) -> Optional[Dict[str, Any]]:
        """
        Get information about the commented object.
        OPTIMIZED: content_type is already prefetched.
        FIXED: Always return object_id as string.
        """
        if not obj.content_object:
            return None
            
        return {
            'content_type': f"{obj.content_type.app_label}.{obj.content_type.model}",
            'object_id': str(obj.object_id),  # Always convert to string
            'object_repr': str(obj.content_object),
        }
    
    def get_is_flagged(self, obj) -> bool:
        """
        Check if the comment has been flagged.
        Uses annotated flags_count_annotated to avoid query.
        """
        # Try to get from annotation first 
        if hasattr(obj, 'flags_count_annotated'):
            return obj.flags_count_annotated > 0
        
        # Fallback for cases without annotation
        # (e.g., when object is created in serializer)
        return obj.flags.exists() if hasattr(obj, 'flags') else False
    
    def create(self, validated_data):
        """
        Create a new comment with content processing.
        Now processes content for profanity and applies auto-flags.
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
        
        # Create the comment
        comment = Comment.objects.create(
            content_type=content_type,
            object_id=object_id,
            **validated_data
        )
        
        # Apply automatic flags if needed
        if flags_to_apply.get('auto_flag_spam') or flags_to_apply.get('auto_flag_profanity'):
            apply_automatic_flags(comment)
        
        return comment
    
    def update(self, instance, validated_data):
        """
        Update a comment.
        
        IMPORTANT: The following fields are immutable and cannot be changed:
        - content_type: The type of object being commented on
        - object_id: The ID of the object being commented on
        - parent: The parent comment (for threading structure)
        - thread_id: The thread identifier
        - path: The materialized path for tree structure
        """
        # Remove immutable fields that should never be updated
        immutable_fields = ['content_type', 'object_id', 'parent', 'thread_id', 'path']
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
    
    def get_is_permanent(self, obj):
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