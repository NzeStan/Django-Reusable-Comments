"""
Test models for django_comments testing.

These models are used as targets for comments in the test suite,
demonstrating compatibility with both integer and UUID primary keys.
"""
import uuid

from django.db import models
from django.urls import reverse
from django.utils import timezone


class TestPost(models.Model):
    """
    A simple blog post model for testing comments with integer primary key.
    
    This model demonstrates that django-reusable-comments works with
    standard Django models using auto-incrementing integer PKs.
    """
    
    title = models.CharField(max_length=200)
    content = models.TextField()
    author = models.ForeignKey(
        'auth.User',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='test_posts'
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    published = models.BooleanField(default=True)
    
    class Meta:
        app_label = 'tests'
        ordering = ['-created_at']
        verbose_name = 'Test Post'
        verbose_name_plural = 'Test Posts'
    
    def __str__(self):
        return self.title
    
    def get_absolute_url(self):
        return reverse('testpost_detail', kwargs={'pk': self.pk})


class TestPostWithUUID(models.Model):
    """
    A blog post model using UUID primary key for testing.
    
    This model demonstrates that django-reusable-comments works seamlessly
    with models using UUID primary keys, which are common in modern Django apps.
    """
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    title = models.CharField(max_length=200)
    content = models.TextField()
    author = models.ForeignKey(
        'auth.User',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='uuid_test_posts'
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    published = models.BooleanField(default=True)
    
    class Meta:
        app_label = 'tests'
        ordering = ['-created_at']
        verbose_name = 'Test Post (UUID)'
        verbose_name_plural = 'Test Posts (UUID)'
    
    def __str__(self):
        return self.title
    
    def get_absolute_url(self):
        return reverse('testpost_uuid_detail', kwargs={'pk': self.pk})