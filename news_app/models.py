from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class SearchKeyword(models.Model):
    """
    Model to store search keywords and their metadata
    """
    keyword = models.CharField(max_length=255)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    last_searched = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('keyword', 'user')
        ordering = ['-last_searched']

    def __str__(self):
        return f"{self.keyword} - {self.user.username}"

class Article(models.Model):
    """
    Model to store news articles
    """
    
    title = models.CharField(max_length=500)
    description = models.TextField()
    url = models.URLField()
    urlToImage = models.URLField(blank=True, null=True)
    published_at = models.DateTimeField()
    source_name = models.CharField(max_length=255)
    source_category = models.CharField(max_length=100, blank=True, null=True)
    language = models.CharField(max_length=10, default='en')
    search_keyword = models.ForeignKey(SearchKeyword, on_delete=models.CASCADE, related_name='articles')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-published_at']
        indexes = [
            models.Index(fields=['published_at']),
            models.Index(fields=['source_name']),
            models.Index(fields=['language']),
        ]

    def __str__(self):
        return self.title
    


class UserQuota(models.Model):
    """
    Model to store user search quotas
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='quota')
    quota_limit = models.IntegerField(default=10)
    used_quota = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.user.username} - {self.used_quota}/{self.quota_limit}"

    def has_quota_remaining(self):
        if self.user.is_staff:
            return True
        return self.used_quota < self.quota_limit

    def increment_quota(self):
        if self.has_quota_remaining():
            self.used_quota += 1
            self.save()
            return True
        return False
