from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from Account.models import CaregiverProfile, JobPosting
from AdminApp.models import BlogPost


class StaticViewSitemap(Sitemap):
    priority = 0.6
    changefreq = 'weekly'

    def items(self):
        return ['home', 'browse', 'browse_jobs', 'how_it_works', 'services', 'blog_index', 'contact', 'privacy', 'terms']

    def location(self, item):
        return reverse(item)


class CaregiverSitemap(Sitemap):
    priority = 0.7
    changefreq = 'daily'

    def items(self):
        return CaregiverProfile.objects.filter(status=CaregiverProfile.STATUS_ACTIVE)

    def lastmod(self, obj):
        return obj.updated_at


class JobSitemap(Sitemap):
    priority = 0.8
    changefreq = 'daily'

    def items(self):
        return JobPosting.objects.filter(status=JobPosting.STATUS_OPEN)

    def lastmod(self, obj):
        return obj.updated_at


class BlogSitemap(Sitemap):
    priority = 0.8
    changefreq = 'weekly'

    def items(self):
        return BlogPost.objects.filter(is_published=True)

    def lastmod(self, obj):
        return obj.updated_at

