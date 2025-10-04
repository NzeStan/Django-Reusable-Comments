"""
Test models for django_comments.
"""
import uuid
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _


class TestPost(models.Model):
    """
    A simple model for testing comments.
    """
    __test__ = False
    title = models.CharField(_('Title'), max_length=100)
    content = models.TextField(_('Content'))
    created_at = models.DateTimeField(_('Created at'), auto_now_add=True)
    
    class Meta:
        verbose_name = _('Test Post')
        verbose_name_plural = _('Test Posts')
    
    def __str__(self):
        return self.title
    
    def get_absolute_url(self):
        return reverse('test_post_detail', args=[self.pk])


class TestPostWithUUID(models.Model):
    """
    A model with UUID primary key for testing.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(_('Title'), max_length=100)
    content = models.TextField(_('Content'))
    created_at = models.DateTimeField(_('Created at'), auto_now_add=True)
    
    class Meta:
        verbose_name = _('Test Post with UUID')
        verbose_name_plural = _('Test Posts with UUID')
    
    def __str__(self):
        return self.title