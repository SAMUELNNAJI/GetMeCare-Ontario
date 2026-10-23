from django.contrib import admin
from .models import Faq, Service, BlogPost, BlogComment


@admin.register(Faq)
class FaqAdmin(admin.ModelAdmin):
    list_display = ['question', 'category', 'is_active', 'order', 'created_at']
    list_filter = ['category', 'is_active', 'created_at']
    search_fields = ['question', 'answer']
    list_editable = ['is_active', 'order']
    list_per_page = 50


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ['title', 'slug', 'rate', 'is_active', 'order', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['title', 'slug', 'short_description', 'description']
    list_editable = ['is_active', 'order', 'rate']
    prepopulated_fields = {'slug': ('title',)}
    list_per_page = 50


@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin):
    list_display = ['title', 'category', 'author_name', 'is_published', 'is_featured', 'views_count', 'published_at']
    list_filter = ['category', 'is_published', 'is_featured', 'published_at']
    search_fields = ['title', 'slug', 'excerpt', 'content', 'tags']
    list_editable = ['is_published', 'is_featured']
    prepopulated_fields = {'slug': ('title',)}
    date_hierarchy = 'published_at'
    list_per_page = 25


@admin.register(BlogComment)
class BlogCommentAdmin(admin.ModelAdmin):
    list_display = ['author_name', 'post', 'parent', 'is_approved', 'created_at']
    list_filter = ['is_approved', 'created_at']
    search_fields = ['author_name', 'author_email', 'content', 'post__title']
    list_editable = ['is_approved']
    raw_id_fields = ['post', 'user', 'parent']
    list_per_page = 50


