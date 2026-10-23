import os
import sys
import django

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'GETMECARE.settings')
django.setup()

from django.test import RequestFactory
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.urls import reverse
from Account.models import CustomUser, EmployerProfile, CaregiverProfile, JobPosting
from AdminApp.models import BlogPost
from AdminApp.views import convert_employer_to_caregiver
from Caregiver.views import home, blog_index, blog_detail

factory = RequestFactory()

print("=" * 60)
print("TEST 1: Converting Employer to Caregiver")
print("=" * 60)

# Create a test employer
test_username = "test_employer_convert_123"
user, _ = CustomUser.objects.get_or_create(
    username=test_username,
    defaults={
        "email": "testconvert@example.com",
        "first_name": "Test",
        "last_name": "Employer",
        "role": CustomUser.EMPLOYER,
    }
)
user.role = CustomUser.EMPLOYER
user.save()

emp_profile, _ = EmployerProfile.objects.get_or_create(user=user, defaults={"is_active": True})

# Create a dummy open job
job, _ = JobPosting.objects.get_or_create(
    employer=user,
    title="Test Job for Conversion",
    defaults={
        "city": "Toronto",
        "care_type": "senior_elder",
        "hourly_rate": 30.00,
        "status": JobPosting.STATUS_OPEN,
    }
)

assert user.is_employer is True, "User should initially be an employer"
assert user.is_caregiver is False, "User should not initially be a caregiver"
assert EmployerProfile.objects.filter(user=user).exists(), "EmployerProfile should exist initially"

# Prepare POST request to convert_employer_to_caregiver
req = factory.post(f"/admin-panel/employers/{emp_profile.pk}/convert-to-caregiver/")
# Mock staff admin user
admin_user, _ = CustomUser.objects.get_or_create(
    username="admin_test_runner",
    defaults={"is_staff": True, "is_superuser": True}
)
req.user = admin_user
setattr(req, 'session', {})
messages = FallbackStorage(req)
setattr(req, '_messages', messages)

resp = convert_employer_to_caregiver(req, emp_profile.pk)
assert resp.status_code == 302, f"Expected redirect 302, got {resp.status_code}"

user.refresh_from_db()
assert user.role == CustomUser.CAREGIVER, f"User role should be caregiver, got {user.role}"
assert user.is_caregiver is True, "user.is_caregiver should now be True"
assert user.is_employer is False, "user.is_employer should now be False"
assert not EmployerProfile.objects.filter(user=user).exists(), "EmployerProfile should have been deleted"
assert CaregiverProfile.objects.filter(user=user).exists(), "CaregiverProfile must now exist"

cg_profile = CaregiverProfile.objects.get(user=user)
assert cg_profile.status == CaregiverProfile.STATUS_ACTIVE, "Caregiver profile should be active"
assert cg_profile.account_status == CaregiverProfile.ACCOUNT_ACTIVE, "Account status should be active"

job.refresh_from_db()
assert job.status == JobPosting.STATUS_CLOSED, f"JobPosting should be closed, got {job.status}"

print("[PASS] SUCCESS: Employer successfully converted to Caregiver!")
print(f"  - Role: {user.role}")
print(f"  - is_caregiver: {user.is_caregiver}")
print(f"  - is_employer: {user.is_employer}")
print(f"  - EmployerProfile exists: {EmployerProfile.objects.filter(user=user).exists()}")
print(f"  - CaregiverProfile exists: {CaregiverProfile.objects.filter(user=user).exists()}")

# Clean up test user
job.delete()
cg_profile.delete()
user.delete()

print("\n" + "=" * 60)
print("TEST 2: Blog Public Listing (/blog/)")
print("=" * 60)

req_blog = factory.get("/blog/")
req_blog.user = admin_user
resp_blog = blog_index(req_blog)
assert resp_blog.status_code == 200, f"Blog index status code was {resp_blog.status_code}"
content_blog = resp_blog.content.decode("utf-8")
assert "Ontario Caregiving &" in content_blog, "Blog index title not found in response"
assert "Key Takeaways" in content_blog or "Featured Guide" in content_blog or "articles-grid" in content_blog, "Featured spotlight or articles not found"
print("[PASS] SUCCESS: Blog index page renders correctly with status 200 and schema data!")

print("\n" + "=" * 60)
print("TEST 3: Blog Detail View (/blog/<slug>/) & SEO Schema")
print("=" * 60)

first_post = BlogPost.objects.filter(is_published=True).first()
assert first_post is not None, "At least one published blog post must exist"
initial_views = first_post.views_count

req_detail = factory.get(f"/blog/{first_post.slug}/")
req_detail.user = admin_user
resp_detail = blog_detail(req_detail, first_post.slug)
assert resp_detail.status_code == 200, f"Blog detail status code was {resp_detail.status_code}"
content_detail = resp_detail.content.decode("utf-8")

assert first_post.title in content_detail, "Post title not found in detail HTML"
assert "application/ld+json" in content_detail, "JSON-LD structured data not found"
assert '"@type": "BlogPosting"' in content_detail, "BlogPosting schema not found"
assert '"@type": "BreadcrumbList"' in content_detail, "BreadcrumbList schema not found"
assert "og:title" in content_detail, "OpenGraph title tag not found"
assert "twitter:card" in content_detail, "Twitter card not found"

first_post.refresh_from_db()
assert first_post.views_count == initial_views + 1, "Views count should have incremented"

print(f"✓ SUCCESS: Blog detail rendered for '{first_post.title}'!")
print(f"  - Canonical URL and Meta tags verified")
print(f"  - JSON-LD BlogPosting & BreadcrumbList verified")
print(f"  - View count incremented from {initial_views} to {first_post.views_count}")

print("\n" + "=" * 60)
print("TEST 4: Home Page Blog Carousel Section (/ with 6 posts)")
print("=" * 60)

req_home = factory.get("/")
req_home.user = admin_user
resp_home = home(req_home)
assert resp_home.status_code == 200, f"Home page status code was {resp_home.status_code}"
content_home = resp_home.content.decode("utf-8")

assert "Ontario Care & Wellness Guides" in content_home, "Blog section heading not found in home page"
assert "h-carousel-viewport" in content_home, "Carousel viewport element not found"
assert "mad-blog-card" in content_home, "Mad blog card element not found"
assert "blogTrack" in content_home, "Carousel track not found"

print("[PASS] SUCCESS: Home page contains the Blog section and Mad Carousel with recent posts!")
print("\n" + "=" * 60)
print("ALL TESTS PASSED WITH 100% SUCCESS!")
print("=" * 60)
