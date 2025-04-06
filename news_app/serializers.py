from rest_framework import serializers
from .models import SearchKeyword, Article, UserQuota
from django.contrib.auth.models import User

class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'confirm_password']

    def validate(self, data):
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError("Passwords do not match")
        return data

    def create(self, validated_data):
        validated_data.pop('confirm_password')
        user = User.objects.create_user(**validated_data)
        return user

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email']

class ArticleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Article
        fields = ['id', 'title', 'description', 'url', 'urlToImage', 'published_at', 
                 'source_name', 'source_category', 'language', 'created_at']

class SearchKeywordSerializer(serializers.ModelSerializer):
    articles = ArticleSerializer(many=True, read_only=True)
    user = UserSerializer(read_only=True)

    class Meta:
        model = SearchKeyword
        fields = ['id', 'keyword', 'user', 'created_at', 'last_searched', 
                 'is_active', 'articles']


class NewsSearchSerializer(serializers.Serializer):
    keyword = serializers.CharField(max_length=255)
    source_name = serializers.CharField(required=False, allow_null=True)
    language = serializers.CharField(required=False, allow_null=True)
    start_date = serializers.DateTimeField(required=False, allow_null=True)
    end_date = serializers.DateTimeField(required=False, allow_null=True) 
    source_category = serializers.CharField(required=False, allow_null=True)
    # sort_publish_date = serializers.BooleanField(required=False, default=False)
    refresh=serializers.BooleanField(required=False, default=False)

class UserQuotaSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserQuota
        fields = ['quota_limit', 'used_quota']

class UserListSerializer(serializers.ModelSerializer):
    quota = UserQuotaSerializer()

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'date_joined', 'last_login', 'is_active', 'quota']
        read_only_fields = ['id', 'date_joined', 'last_login', 'is_active']

class UserStatusUpdateSerializer(serializers.Serializer):
    is_active = serializers.BooleanField(required=False)
    user_id = serializers.IntegerField(required=True)
    user_quota = serializers.IntegerField(required=False, min_value=0)

    def validate_user_id(self, value):
        try:
            user = User.objects.get(id=value)
            if user.is_staff:
                raise serializers.ValidationError("Cannot update status for staff users")
            return value
        except User.DoesNotExist:
            raise serializers.ValidationError("User does not exist")

class TopKeywordsSerializer(serializers.Serializer):
    keyword = serializers.CharField()
    count = serializers.IntegerField()

 