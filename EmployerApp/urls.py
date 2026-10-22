from django.urls import path
from . import views

app_name = 'EmployerApp'

urlpatterns = [
    path('employer/',
          views.dashboard,          name='dashboard'),
    path('employer/shifts/',
          views.my_shifts,          name='my_shifts'),
    path('employer/shifts/<int:shift_id>/review/', views.submit_caregiver_review, name='submit_caregiver_review'),
    path('employer/payments/',
           views.payment_history,    name='payment_history'),
    path('employer/post-job/',
            views.post_job,           name='post_job'),
    path('employer/my-jobs/',
            views.my_jobs,            name='my_jobs'),
    path('employer/jobs/<int:job_id>/close/',   views.close_job,          name='close_job'),
    path('employer/activate/',
            views.activate_account,   name='activate_account'),
    path('employer/pay-later/',
            views.pay_later,          name='pay_later'),
    path('employer/snooze-first-job/',
            views.snooze_first_job_modal, name='snooze_first_job'),
    path('employer/dismiss-first-job/',
            views.dismiss_first_job_modal, name='dismiss_first_job'),

    # Booking flow
    path('employer/book/<int:proposal_pk>/',
            views.book_caregiver,    name='book_caregiver'),
    path('employer/checkout/<int:shift_pk>/',
            views.payment_checkout,  name='payment_checkout'),
    path('employer/checkout/<int:shift_pk>/confirm/',
            views.confirm_payment,   name='confirm_payment'),

    # Disputes
    path('employer/disputes/',
                  views.my_disputes,
          name='my_disputes'),
    path('employer/disputes/submit/',
                 views.submit_dispute,
                 name='submit_dispute'),

    # Admin shift-log console
    path('employer/admin/shift-log/',
                 views.admin_shift_log,
                 name='admin_shift_log'),

    #  Stripe Payment Link for candidate selection
    path('employer/pay-later/start/',
                 views.start_39_payment_link,
                 name='start_39_payment_link'),

    # Stripe payment callbacks (redirect after hosted checkout)
    path('employer/stripe/activation/checkout/',
         views.stripe_activation_checkout,  name='stripe_activation_checkout'),
    path('employer/stripe/activation/callback/',
         views.stripe_activation_callback,  name='stripe_activation_callback'),
    path('employer/stripe/booking/<int:shift_pk>/checkout/',
         views.stripe_booking_checkout,     name='stripe_booking_checkout'),
    path('employer/stripe/booking/<int:shift_pk>/callback/',
         views.stripe_booking_callback,     name='stripe_booking_callback'),

    # Stripe webhook - called by Stripe's servers (not the browser)
    path('webhooks/stripe/',
         views.stripe_webhook,
         name='stripe_webhook'),

    # Admin notification webhook - called from unified signup form
    path('webhooks/request-notification/',
         views.request_notification_webhook,
         name='request_notification_webhook'),
]
