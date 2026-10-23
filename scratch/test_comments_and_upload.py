import os
import sys
sys.path.insert(0, os.path.abspath('.'))
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'GETMECARE.settings')
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from AdminApp.models import BlogPost, BlogComment

User = get_user_model()
client = Client()

post = BlogPost.objects.filter(is_published=True).first()
print(f"Testing with post: {post.title} (slug: {post.slug})")

# Clean up or check existing comments
initial_count = post.comments.count()
print(f"Initial comments count on post: {initial_count}")

# Add dummy top-level comments to reach > 5 for pagination test
created_comments = []
if post.comments.filter(is_approved=True, parent=None).count() < 8:
    for i in range(1, 9):
        c = BlogComment.objects.create(
            post=post,
            author_name=f"Tester {i}",
            content=f"This is test comment #{i} to verify Ontario care advice and pagination functionality.",
            is_approved=True
        )
        created_comments.append(c)
    print(f"Added {len(created_comments)} dummy comments for pagination test.")

# 1. Test public blog detail GET
detail_url = reverse('blog_detail', kwargs={'slug': post.slug})
resp = client.get(detail_url)
assert resp.status_code == 200, f"Detail page failed with status {resp.status_code}"
assert b'commentsListContainer' in resp.content, "Missing #commentsListContainer"
assert b'cmt-pagination' in resp.content, "Missing .cmt-pagination on page with > 5 comments"
print("[PASS] Public blog detail renders comments list and pagination bar!")

# 2. Test Ajax pagination request for c_page=2
resp_ajax = client.get(detail_url + '?c_page=2', HTTP_X_REQUESTED_WITH='XMLHttpRequest')
assert resp_ajax.status_code == 200, f"Ajax pagination failed with {resp_ajax.status_code}"
data = resp_ajax.json()
assert data.get('success') is True, "Ajax response success is not True"
assert data.get('current_page') == 2, f"Expected page 2, got {data.get('current_page')}"
assert 'comment-item' in data.get('comments_html', ''), "Missing comment-item in comments_html"
assert 'cmt-pagination' in data.get('comments_html', ''), "Missing cmt-pagination in comments_html"
print("[PASS] Ajax comment pagination returned JSON with comments_html and page 2 metadata!")

# 3. Test Admin blog post create/edit form
admin_user = User.objects.filter(is_staff=True).first()
if not admin_user:
    admin_user = User.objects.create_superuser('testadmin_blog', 'testadmin_blog@example.com', 'AdminPass123!')
client.force_login(admin_user)

form_url = reverse('AdminApp:blog_edit', kwargs={'post_id': post.pk})
resp_admin = client.get(form_url)
assert resp_admin.status_code == 200, f"Admin blog edit form failed with {resp_admin.status_code}"
assert b'custom-file-uploader' in resp_admin.content, "Missing .custom-file-uploader in blog-form"
assert b'upload-action-btn' in resp_admin.content, "Missing .upload-action-btn in blog-form"
assert b'Browse Files' in resp_admin.content, "Missing 'Browse Files' button in blog-form"
assert b'uploadPreviewCard' in resp_admin.content, "Missing #uploadPreviewCard in blog-form"
print("[PASS] Admin blog post form renders styled upload button and dropzone component!")

# Clean up temporary test comments if desired
for c in created_comments:
    c.delete()
print("[DONE] All checks passed successfully!")
