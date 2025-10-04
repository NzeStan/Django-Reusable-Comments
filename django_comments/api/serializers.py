from typing import Dict, Any, Optional
from django.contrib.contenttypes.models import ContentType
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from ..conf import comments_settings
from ..exceptions import MaximumThreadDepthExceeded, CommentDisallowed
from ..models import CommentFlag
from ..utils import (
    get_comment_model,
    get_model_from_content_type_string,
    get_object_from_content_type_and_id,
    is_comment_content_allowed,
    filter_profanity
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
    Serializer for comment flags.
    """
    flag_type = serializers.ChoiceField(
        source='flag',
        choices=CommentFlag.FLAG_CHOICES
    )
    
    class Meta:
        model = CommentFlag
        fields = ('id', 'flag_type', 'reason', 'created_at')
        read_only_fields = ('id', 'created_at')


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
    Serializer for handling children comments recursively.
    """
    def to_representation(self, value):
        serializer = CommentSerializer(value, context=self.context)
        return serializer.data


class CommentSerializer(serializers.ModelSerializer):
    """
    Serializer for comments with support for nested comments.
    """

    content_type = serializers.CharField(
        write_only=True,
        help_text=_("Content type in the format 'app_label.model_name'")
    )
    object_id = serializers.CharField(
        write_only=True,
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

    flags_count = serializers.SerializerMethodField()
    is_flagged = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = (
            'id', 'content', 'content_type', 'object_id', 'content_object_info', 
            'user', 'user_info', 'user_name', 'user_email', 'user_url',
            'parent', 'children', 'depth', 'thread_id',
            'created_at', 'updated_at', 'is_public', 'is_removed',
            'flags_count', 'is_flagged',
        )
        read_only_fields = (
            'id', 'content_object_info', 'user_info', 'children', 'thread_id',
            'depth', 'created_at', 'updated_at', 'is_flagged',
        )

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
            raise MaximumThreadDepthExceeded(max_depth=max_depth)
            
        return value
    
    def validate_content(self, value):
        """
        Validate that the comment content is allowed.
        """
        if not is_comment_content_allowed(value):
            raise CommentDisallowed(
                _("Comment content is not allowed (may contain spam or profanity)")
            )
        
        # Filter profanity if enabled
        return filter_profanity(value)
    
    def validate_object_id(self, value):
        """
        Validate object_id format if needed.
        """
        # If you want to ensure it's a valid UUID when USE_UUIDS is True
        if comments_settings.USE_UUIDS:
            import uuid
            try:
                uuid.UUID(value)  # Just validate, don't convert
            except ValueError:
                raise serializers.ValidationError("Invalid UUID format")
        return value
    
    def validate_content_type(self, value):
        """
        Validate that the content type is allowed.
        """
        print(f"Validating content type: '{value}'")
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
        """
        request = self.context.get("request")
        user = data.get("user")

        # If explicitly passed or auto-filled by CurrentUserDefault
        if user and not user.is_authenticated:
            data["user"] = None

        is_anonymous = not data.get("user")

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
            user = data["user"]
            data["user_name"] = user.get_full_name() or user.get_username()
            data["user_email"] = user.email
            data["user_url"] = self.get_user_url(user)

        if comments_settings.MODERATOR_REQUIRED:
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
        """
        if not obj.content_object:
            return None
            
        return {
            'content_type': f"{obj.content_type.app_label}.{obj.content_type.model}",
            'object_id': obj.object_id,
            'object_repr': str(obj.content_object),
        }
    
    def get_flags_count(self, obj) -> int:
        """
        Get the number of flags for the comment.
        """
        return obj.flags.count()
    
    def get_is_flagged(self, obj) -> bool:
        """
        Check if the comment has been flagged.
        """
        return obj.flags.exists()
    
    def create(self, validated_data):
        """
        Create a new comment.
        """
        # Extract content_type and object_id
        content_type_str = validated_data.pop('content_type')
        object_id = validated_data.pop('object_id')
        
        # Get the content type and object
        model = get_model_from_content_type_string(content_type_str)
        content_type = ContentType.objects.get_for_model(model)
        
        # Create the comment
        comment = Comment.objects.create(
            content_type=content_type,
            object_id=object_id,
            **validated_data
        )
        
        return comment