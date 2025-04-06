from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, DetailView
from django.utils import timezone
from datetime import timedelta
import requests
from django.conf import settings
from .models import SearchKeyword, Article, UserQuota
from django.db.models import Q
from django.contrib import messages
from django.core.paginator import Paginator
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Count
from .serializers import (
    ArticleSerializer, NewsSearchSerializer, UserRegistrationSerializer, UserListSerializer, UserStatusUpdateSerializer, TopKeywordsSerializer
)
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.contrib.auth.models import User

class AdvancedNewsSearchAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        quota_obj = UserQuota.objects.get(user=request.user)
        if not quota_obj.has_quota_remaining():
            return Response({
                'success': False,
                'message': 'Quota limit reached',
                'data': None
            }, status=status.HTTP_403_FORBIDDEN)

        serializer = NewsSearchSerializer(data=request.data)
        print(f'\n\n{serializer=}\n\n')

        if serializer.is_valid():
            keyword = serializer.validated_data['keyword']
            source_name = serializer.validated_data.get('source_name')
            language = serializer.validated_data.get('language')
            start_date = serializer.validated_data.get('start_date')
            end_date = serializer.validated_data.get('end_date')
            # sort_publish_date = serializer.validated_data.get('sort_publish_date')
            refresh=serializer.validated_data.get('refresh')
            print(f'\n\n{refresh=}\n\n')
            # Check if keyword exists and is within time threshold
            search_keyword = SearchKeyword.objects.filter(
                keyword=keyword,
                user=request.user
            ).first()
            print(f'\n\n{search_keyword=}\n\n')
            print(f'\n\n{request.data=}\n\n')
            # print(f'\n\n{sort_publish_date=}\n\n')
            if search_keyword and not refresh:
                time_diff = timezone.now() - search_keyword.last_searched
                if time_diff < timedelta(minutes=15):
                    # Get articles directly from the search keyword
                    articles = Article.objects.filter(search_keyword=search_keyword).order_by('-published_at')
                    
                    # Apply filters if provided
                    # if sort_publish_date:
                    #     articles = articles.order_by('-published_at')
                    if source_name:
                        articles = articles.filter(source_name=source_name)
                    if language:
                        articles = articles.filter(language=language)
                    if start_date:
                        articles = articles.filter(published_at__date__gte=start_date)
                    if end_date:
                        articles = articles.filter(published_at__date__lte=end_date)

                    print(f'\n\n{request.user=}\n\n')
                    existing_keyword = SearchKeyword.objects.filter(keyword=keyword, user=request.user).first()
                    existing_keyword.last_searched = timezone.now()
                    existing_keyword.save()
                    return Response({
                        'success': True,
                        'message': 'Using cached data',
                        'data': {
                            'keyword': keyword,
                            'articles': ArticleSerializer(articles, many=True).data
                        }
                    })
            
            # If no cached data or cache expired, fetch from API
            is_search_keyword_created = False
            if not search_keyword:
                search_keyword = SearchKeyword.objects.create(
                    keyword=keyword,
                    user=request.user
                )
                is_search_keyword_created = True
            else:
                search_keyword.last_searched = timezone.now()
                search_keyword.save()
            
            # Build News API URL with filters
            url = f'https://newsapi.org/v2/everything?q={keyword}&apiKey={settings.NEWS_API_KEY}'
            # if source_name:
            #     url += f'&sources={source_name}'
            # if language:
            #     url += f'&language={language}'
            # if start_date:
            #     url += f'&from={start_date}'
            # if end_date:
            #     url += f'&to={end_date}'
            if refresh or (is_search_keyword_created == False):
                articles = Article.objects.order_by('-published_at').filter(search_keyword=search_keyword).first()
                # url += f'&refresh=true'
                url += f'&from={articles.published_at.date()}'
            response = requests.get(url)
            
            if response.status_code == 200:
                data = response.json()
                articles_data = data.get('articles', [])
                print(f'\n\n{articles_data=}\n\n')
                # Create articles in bulk
                articles_to_create = []
                for article_data in articles_data:
                    article = Article(
                        title=article_data['title'],
                        description=article_data['description'],
                        url=article_data['url'],
                        urlToImage=article_data['urlToImage'],
                        published_at=article_data['publishedAt'],
                        source_name=article_data['source']['name'],
                        source_category=article_data.get('source', {}).get('category'),
                        language=article_data.get('language', 'en'),
                        search_keyword=search_keyword  # Direct relationship
                    )
                    articles_to_create.append(article)
                
                # Bulk create articles
                created_articles = Article.objects.bulk_create(
                    articles_to_create,
                    ignore_conflicts=True
                )
                
                articles = Article.objects.filter(search_keyword=search_keyword)
                
                # Apply filters if provided
                if source_name:
                    articles = articles.filter(source_name=source_name)
                if language:
                    articles = articles.filter(language=language)
                if start_date:
                    articles = articles.filter(published_at__date__gte=start_date)
                if end_date:
                    articles = articles.filter(published_at__date__lte=end_date)
                
                return Response({
                    'success': True,
                    'message': 'Data fetched from API',
                    'data': {
                        'keyword': keyword,
                        'articles': ArticleSerializer(articles, many=True).data
                    }
                })
                
                
            
            return Response({
                'success': False,
                'message': 'Error fetching news from API',
                'data': None
            }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response({
            'success': False,
            'message': 'Invalid search parameters',
            'errors': serializer.errors,
            'data': None
        }, status=status.HTTP_400_BAD_REQUEST)


class UserRegistrationAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            
            # Create UserQuota entry for the new user
            UserQuota.objects.create(user=user, quota_limit=10, used_quota=0)
            
            refresh = RefreshToken.for_user(user)
            return Response({
                'success': True,
                'message': 'Registration successful',
                'data': {
                    'user': {
                        'id': user.id,
                        'username': user.username,
                        'email': user.email,
                        'is_staff': user.is_staff
                    },
                    'tokens': {
                        'access': str(refresh.access_token),
                        'refresh': str(refresh)
                    }
                }
            }, status=status.HTTP_201_CREATED)
        
        return Response({
            'success': False,
            'message': 'Registration failed',
            'errors': serializer.errors,
            'data': None
        }, status=status.HTTP_400_BAD_REQUEST)

class UserLoginAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')

        if not username or not password:
            return Response({
                'success': False,
                'message': 'Please provide both username and password',
                'data': None
            }, status=status.HTTP_400_BAD_REQUEST)

        user = authenticate(username=username, password=password)
        
        if user and user.is_active:
            refresh = RefreshToken.for_user(user)
            return Response({
                'success': True,
                'message': 'Login successful',
                'data': {
                    'user': {
                        'id': user.id,
                        'username': user.username,
                        'email': user.email,
                        'is_staff': user.is_staff
                    },
                    'tokens': {
                        'access': str(refresh.access_token),
                        'refresh': str(refresh)
                    }
                }
            })
        
        return Response({
            'success': False,
            'message': 'Invalid credentials',
            'data': None
        }, status=status.HTTP_401_UNAUTHORIZED)


class UserSearchHistoryAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """
        Get user's search history (keywords only)
        """
        # Get all search keywords for the user
        search_keywords = SearchKeyword.objects.filter(
            user=request.user
        ).order_by('-last_searched')

        # Create simple list of keywords with their search times
        search_history = [
            {
                'keyword': keyword.keyword,
                'last_searched': keyword.last_searched
            }
            for keyword in search_keywords
        ]

        return Response({
            'success': True,
            'message': 'Search history retrieved successfully',
            'data': {
                'search_history': search_history
            }
        })

class UserListAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """
        List all non-staff users with their quota information (only accessible by staff users)
        """
        # Check if the requesting user is staff
        if not request.user.is_staff:
            return Response({
                'success': False,
                'message': 'Only staff users can access this endpoint',
                'data': None
            }, status=status.HTTP_403_FORBIDDEN)

        # Get all non-staff users with their quota information
        users = User.objects.filter(is_staff=False).select_related('quota')
        
        # Serialize the users
        serializer = UserListSerializer(users, many=True)

        return Response({
            'success': True,
            'message': 'Users retrieved successfully',
            'data': {
                'users': serializer.data
            }
        })

class UserManagementAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request):
        """
        Update user status and quota (only accessible by staff users)
        """
        # Check if the requesting user is staff
        if not request.user.is_staff:
            return Response({
                'success': False,
                'message': 'Only staff users can access this endpoint',
                'data': None
            }, status=status.HTTP_403_FORBIDDEN)

        serializer = UserStatusUpdateSerializer(data=request.data)
        if serializer.is_valid():
            user_id = serializer.validated_data['user_id']
            is_active = serializer.validated_data.get('is_active')
            user_quota = serializer.validated_data.get('user_quota')

            try:
                user = User.objects.get(id=user_id)
                response_data = {}

                # Update is_active if provided
                if is_active is not None:
                    user.is_active = is_active
                    user.save()
                    response_data['is_active'] = is_active

                # Update quota if provided
                if user_quota is not None:
                    user_quota_obj, created = UserQuota.objects.get_or_create(user=user)
                    user_quota_obj.quota_limit = user_quota
                    user_quota_obj.save()
                    response_data['quota_limit'] = user_quota

                return Response({
                    'success': True,
                    'message': 'User updated successfully',
                    'data': response_data
                })
            except User.DoesNotExist:
                return Response({
                    'success': False,
                    'message': 'User not found',
                    'data': None
                }, status=status.HTTP_404_NOT_FOUND)

        return Response({
            'success': False,
            'message': 'Invalid data',
            'errors': serializer.errors,
            'data': None
        }, status=status.HTTP_400_BAD_REQUEST)

class TopKeywordsAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """
        Get top 5 most searched keywords with their counts (only accessible by staff users)
        """
        # Check if the requesting user is staff
        if not request.user.is_staff:
            return Response({
                'success': False,
                'message': 'Only staff users can access this endpoint',
                'data': None
            }, status=status.HTTP_403_FORBIDDEN)

        # Get top 5 keywords with their counts
        top_keywords = SearchKeyword.objects.values('keyword').annotate(
            count=Count('keyword')
        ).order_by('-count')[:5]

        # Serialize the data
        serializer = TopKeywordsSerializer(top_keywords, many=True)

        return Response({
            'success': True,
            'message': 'Top keywords retrieved successfully',
            'data': {
                'top_keywords': serializer.data
            }
        })

