from django.urls import path
from . import views

app_name = "Account"
urlpatterns = [
    path('signup/',              views.signup,              name='signup'),
    path('login/',               views.login_view,          name='login'),
    path('logout/',              views.logout_view,         name='logout'),
    path('admin-dashboard/',     views.admin_dashboard,     name='admin_dashboard'),
    path('employer-dashboard/',  views.employer_dashboard,  name='employer_dashboard'),
    path('caregiver-dashboard/', views.caregiver_dashboard, name='caregiver_dashboard'),
    path('clock-in/',            views.clock_in,            name='clock_in'),
    path('clock-out/',           views.clock_out,           name='clock_out'),
    path('edit-profile/',        views.edit_profile,        name='edit_profile'),
    path('documents/',           views.documents,           name='documents'),
    path('change-password/',     views.password_change,     name='password_change'),
    path('notifications/',       views.get_notifications,    name='get_notifications'),
    path('notifications/clear/', views.clear_notifications,  name='clear_notifications'),
    path('notifications/<int:notif_id>/dismiss/', views.dismiss_notification, name='dismiss_notification'),
    path('update-whatsapp/',     views.update_user_whatsapp, name='update_user_whatsapp'),
    path('dismiss-whatsapp/',    views.dismiss_whatsapp_modal, name='dismiss_whatsapp_modal'),
]

