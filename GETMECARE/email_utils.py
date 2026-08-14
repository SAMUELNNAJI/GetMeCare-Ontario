"""
GETMECARE — Centralised transactional email helpers.

All outbound mail goes through send_transactional_email() which uses
Django's built-in SMTP backend configured for ZeptoMail.

Trigger points
-------------
• signup                       → send_welcome_email()
• password changed             → send_password_changed_email()
• clock-in                     → send_clock_in_email()
• clock-out                    → send_clock_out_email()
• shift payment confirmed       → send_shift_payment_employer_email()
                                   send_shift_payment_caregiver_email()
• employer activation payment  → send_activation_confirmation_email()
• direct chat (offline)        → send_offline_chat_notification()
• support chat (offline)       → send_support_offline_notification()
• support chat resolved        → send_support_resolved_email()
• admin marks payout paid      → send_payout_notification_email()
• employer submits dispute     → send_dispute_submitted_admin_email()
• admin resolves/dismisses     → send_dispute_resolved_employer_email()
• (password reset uses Django's built-in PasswordResetView — no helper needed)
• password changed successfully   → send_password_changed_email()
"""

from __future__ import annotations

import logging
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils import timezone

logger = logging.getLogger(__name__)

ADMIN_EMAIL: str = getattr(settings, 'ADMIN_EMAIL', 'info@getmecare-ontario.com')
FROM_EMAIL: str  = getattr(settings, 'DEFAULT_FROM_EMAIL', 'GetMeCare Ontario <noreply@getmecare-ontario.com>')
SITE_NAME         = 'GetMeCare Ontario'
SITE_URL          = 'https://getmecare-ontario.com'


# ──────────────────────────────────────────────────────────────
# Internal sender
# ──────────────────────────────────────────────────────────────

def send_transactional_email(
    subject: str,
    to_email: str | list[str],
    html_body: str,
    plain_body: str = '',
) -> bool:
    """Send one transactional email.  Returns True on success, False on error."""
    if isinstance(to_email, str):
        to_email = [to_email]

    plain_body = plain_body or _strip_html(html_body)

    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=plain_body,
            from_email=FROM_EMAIL,
            to=to_email,
        )
        msg.attach_alternative(html_body, 'text/html')
        msg.send(fail_silently=False)
        logger.info('Email sent — subject="%s" to=%s', subject, to_email)
        return True
    except Exception:
        logger.exception('Email send failed — subject="%s" to=%s', subject, to_email)
        return False


def _strip_html(html: str) -> str:
    """Very lightweight HTML → plain-text (removes tags only)."""
    import re
    return re.sub(r'<[^>]+>', '', html).strip()


# ──────────────────────────────────────────────────────────────
# Shared HTML wrapper
# ──────────────────────────────────────────────────────────────

def _wrap(content: str) -> str:
    """Wrap content in a branded HTML email shell with logo visible in Gmail.

    Uses a hybrid approach:
    - <style> block in <head> for email clients that support it (Outlook, Apple Mail)
    - Inline styles on structural elements for Gmail which strips <style> blocks
    - Logo rendered as a hosted absolute-URL image so it shows everywhere
    """
    year = timezone.now().year
    logo_url = 'https://getmecare-ontario.com/static/Caregiver/images/sitelog.png'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{SITE_NAME}</title>
  <style>
    body {{ margin:0; padding:0; background:#f4f6f9; font-family:Arial,sans-serif; }}
    h2   {{ margin-top:0; color:#1a6b4a; font-size:18px; }}
    .info-box {{ background:#f0f9f4; border-left:4px solid #1a6b4a;
                 padding:14px 18px; border-radius:4px; margin:20px 0; }}
    .info-box p {{ margin:4px 0; }}
    .btn {{ display:inline-block; margin-top:20px; padding:12px 28px;
            background:#1a6b4a; color:#ffffff !important; text-decoration:none;
            border-radius:5px; font-size:15px; font-weight:bold; }}
  </style>
</head>
<body style="margin:0;padding:0;background:#f4f6f9;font-family:Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f6f9;padding:24px 0;">
    <tr>
      <td align="center">
        <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:#ffffff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.08);">

          <!-- HEADER with logo -->
          <tr>
            <td style="background:#1a6b4a;padding:22px 32px;text-align:center;">
              <table cellpadding="0" cellspacing="0" style="margin:0 auto;">
                <tr>
                  <td style="vertical-align:middle;padding-right:10px;">
                    <img src="{logo_url}"
                         alt="{SITE_NAME}"
                         width="36" height="36"
                         style="display:block;width:36px;height:36px;object-fit:contain;border:0;" />
                  </td>
                  <td style="vertical-align:middle;">
                    <span style="font-size:20px;font-weight:700;color:#ffffff;letter-spacing:.4px;font-family:Arial,sans-serif;">
                      GetMe<span style="color:#F0A040;">Care</span>
                    </span>
                    <div style="font-size:9px;letter-spacing:.14em;color:#8fbfaa;text-transform:uppercase;margin-top:2px;font-family:Arial,sans-serif;">
                      Ontario
                    </div>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- BODY -->
          <tr>
            <td style="padding:32px;color:#333333;font-size:15px;line-height:1.7;font-family:Arial,sans-serif;">
              {content}
            </td>
          </tr>

          <!-- FOOTER -->
          <tr>
            <td style="background:#f4f6f9;text-align:center;padding:18px 32px;font-size:12px;color:#888888;font-family:Arial,sans-serif;">
              &copy; {year} {SITE_NAME} &nbsp;|&nbsp;
              <a href="{SITE_URL}" style="color:#1a6b4a;text-decoration:none;">{SITE_URL}</a><br />
              Questions? Email us at
              <a href="mailto:{ADMIN_EMAIL}" style="color:#1a6b4a;text-decoration:none;">{ADMIN_EMAIL}</a>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


# ──────────────────────────────────────────────────────────────
# 1. Welcome email  (fired on signup)
# ──────────────────────────────────────────────────────────────

def send_welcome_email(user) -> bool:
    role_label = 'Employer / Family' if user.is_employer else 'Caregiver / PSW'
    dashboard_url = f'{SITE_URL}/login/'

    content = f"""
    <h2>Welcome to {SITE_NAME}, {user.first_name or user.username}!</h2>
    <p>Your account has been created successfully. Here's a quick summary:</p>
    <div class="info-box">
      <p><strong>Name:</strong> {user.get_full_name() or user.username}</p>
      <p><strong>Email:</strong> {user.email}</p>
      <p><strong>Account type:</strong> {role_label}</p>
    </div>
    <p>
      {'As an <strong>Employer</strong>, you can now post job offers, browse verified caregivers, and book shifts directly through the platform.'
       if user.is_employer else
       'As a <strong>Caregiver</strong>, please complete your profile and upload your documents so our team can verify your account.'}
    </p>
    <a class="btn" href="{dashboard_url}">Go to My Dashboard</a>
    <p style="margin-top:24px;">If you have any questions, reply to this email or contact us at
       <a href="mailto:{ADMIN_EMAIL}">{ADMIN_EMAIL}</a>.</p>
    """
    return send_transactional_email(
        subject=f'Welcome to {SITE_NAME} — Your account is ready',
        to_email=user.email,
        html_body=_wrap(content),
    )


# ──────────────────────────────────────────────────────────────
# 1a. Password changed confirmation
#      (fired after user successfully changes password)
# ──────────────────────────────────────────────────────────────

def send_password_changed_email(user) -> bool:
    profile_url = f'{SITE_URL}/edit-profile/'
    changed_str = timezone.localtime(timezone.now()).strftime('%B %d, %Y at %I:%M %p')

    content = f"""
    <h2>Your password has been changed</h2>
    <p>Hi {user.first_name or user.username}, this is a confirmation that your
       {SITE_NAME} account password was successfully changed.</p>
    <div class="info-box">
      <p><strong>Account:</strong> {user.get_full_name() or user.username}</p>
      <p><strong>Email:</strong> {user.email}</p>
      <p><strong>Changed on:</strong> {changed_str}</p>
    </div>
    <p>If you made this change, no further action is needed.</p>
    <p>If you did <strong>not</strong> change your password, your account may have
       been compromised. Please secure your account immediately by:</p>
    <ul style="padding-left:20px;line-height:2;">
      <li>Contacting us at <a href="mailto:{ADMIN_EMAIL}">{ADMIN_EMAIL}</a></li>
      <li>Reviewing any recent account activity</li>
    </ul>
    <a class="btn" href="{profile_url}">Go to My Profile</a>
    """
    return send_transactional_email(
        subject=f'[{SITE_NAME}] Your password has been changed',
        to_email=user.email,
        html_body=_wrap(content),
    )


# ──────────────────────────────────────────────────────────────
# 2. Clock-in notification  (fired when caregiver clocks in)
# ──────────────────────────────────────────────────────────────

def send_clock_in_email(user, shift) -> bool:
    now_str = timezone.localtime(timezone.now()).strftime('%B %d, %Y at %I:%M %p')

    content = f"""
    <h2>You have clocked in — Shift #{shift.pk}</h2>
    <p>Hi {user.first_name or user.username}, this is a confirmation that you have successfully clocked in.</p>
    <div class="info-box">
      <p><strong>Shift #:</strong> {shift.pk}</p>
      <p><strong>Date:</strong> {shift.start_date.strftime('%B %d, %Y')}</p>
      <p><strong>Clock-in time:</strong> {now_str}</p>
      <p><strong>Employer:</strong> {shift.employer.get_full_name()}</p>
      <p><strong>Location:</strong> {shift.city or 'Ontario'}</p>
      <p><strong>Duration booked:</strong> {shift.duration_hours} hrs @ ${shift.hourly_rate}/hr</p>
    </div>
    <p>Have a great shift! If anything comes up, contact the platform at
       <a href="mailto:{ADMIN_EMAIL}">{ADMIN_EMAIL}</a>.</p>
    """
    # Notify caregiver
    sent = send_transactional_email(
        subject=f'[{SITE_NAME}] Clock-in confirmed — Shift #{shift.pk}',
        to_email=user.email,
        html_body=_wrap(content),
    )

    # Notify admin
    admin_content = f"""
    <h2>Caregiver Clock-In Alert</h2>
    <div class="info-box">
      <p><strong>Caregiver:</strong> {user.get_full_name()} ({user.email})</p>
      <p><strong>Shift #:</strong> {shift.pk}</p>
      <p><strong>Date:</strong> {shift.start_date.strftime('%B %d, %Y')}</p>
      <p><strong>Clock-in time:</strong> {now_str}</p>
      <p><strong>Employer:</strong> {shift.employer.get_full_name()}</p>
    </div>
    """
    send_transactional_email(
        subject=f'[Admin] Caregiver clocked in — Shift #{shift.pk}',
        to_email=ADMIN_EMAIL,
        html_body=_wrap(admin_content),
    )
    return sent


# ──────────────────────────────────────────────────────────────
# 3. Clock-out notification  (fired when caregiver clocks out)
# ──────────────────────────────────────────────────────────────

def send_clock_out_email(user, shift, log) -> bool:
    now_str = timezone.localtime(timezone.now()).strftime('%B %d, %Y at %I:%M %p')

    content = f"""
    <h2>You have clocked out — Shift #{shift.pk}</h2>
    <p>Hi {user.first_name or user.username}, great work today! Here is your shift summary:</p>
    <div class="info-box">
      <p><strong>Shift #:</strong> {shift.pk}</p>
      <p><strong>Date:</strong> {shift.start_date.strftime('%B %d, %Y')}</p>
      <p><strong>Clock-out time:</strong> {now_str}</p>
      <p><strong>Hours worked (actual):</strong> {log.hours_worked} hrs</p>
      <p><strong>Earnings (85% of booked):</strong> <strong>${log.amount_earned} CAD</strong></p>
      <p><strong>Payment status:</strong> Pending — will be settled by admin</p>
    </div>
    <p>Your earnings will be processed by the admin team. If you have any concerns,
       contact us at <a href="mailto:{ADMIN_EMAIL}">{ADMIN_EMAIL}</a>.</p>
    """
    sent = send_transactional_email(
        subject=f'[{SITE_NAME}] Clock-out confirmed — Shift #{shift.pk}',
        to_email=user.email,
        html_body=_wrap(content),
    )

    # Notify admin
    admin_content = f"""
    <h2>Caregiver Clock-Out Alert</h2>
    <div class="info-box">
      <p><strong>Caregiver:</strong> {user.get_full_name()} ({user.email})</p>
      <p><strong>Shift #:</strong> {shift.pk}</p>
      <p><strong>Date:</strong> {shift.start_date.strftime('%B %d, %Y')}</p>
      <p><strong>Clock-out time:</strong> {now_str}</p>
      <p><strong>Hours worked:</strong> {log.hours_worked} hrs</p>
      <p><strong>Earnings due:</strong> ${log.amount_earned} CAD</p>
    </div>
    <p>Please review and process payment for this caregiver.</p>
    """
    send_transactional_email(
        subject=f'[Admin] Caregiver clocked out — Shift #{shift.pk} — action required',
        to_email=ADMIN_EMAIL,
        html_body=_wrap(admin_content),
    )
    return sent


# ──────────────────────────────────────────────────────────────
# 4. Shift payment — employer confirmation
# ──────────────────────────────────────────────────────────────

def send_shift_payment_employer_email(employer, shift, payment) -> bool:
    content = f"""
    <h2>Payment Confirmed — Shift #{shift.pk}</h2>
    <p>Hi {employer.first_name or employer.username}, your payment has been received and your shift is now confirmed.</p>
    <div class="info-box">
      <p><strong>Payment reference:</strong> {payment.payment_reference}</p>
      <p><strong>Shift #:</strong> {shift.pk}</p>
      <p><strong>Caregiver:</strong> {shift.caregiver.get_full_name()}</p>
      <p><strong>Date:</strong> {shift.start_date.strftime('%B %d, %Y')}</p>
      <p><strong>Start time:</strong> {shift.start_time.strftime('%I:%M %p')}</p>
      <p><strong>Duration:</strong> {shift.duration_hours} hrs</p>
      <p><strong>Rate:</strong> ${shift.hourly_rate}/hr</p>
      <p><strong>Amount charged:</strong> <strong>${payment.amount} CAD</strong></p>
      <p><strong>Location:</strong> {shift.city or 'Ontario'}</p>
    </div>
    <p>The caregiver has been notified and will arrive as scheduled.
       For any changes or concerns, contact us at
       <a href="mailto:{ADMIN_EMAIL}">{ADMIN_EMAIL}</a>.</p>
    <a class="btn" href="{SITE_URL}/employer/shifts/">View My Shifts</a>
    """
    return send_transactional_email(
        subject=f'[{SITE_NAME}] Payment confirmed — Shift #{shift.pk} booked',
        to_email=employer.email,
        html_body=_wrap(content),
    )


# ──────────────────────────────────────────────────────────────
# 5. Shift payment — caregiver notification
# ──────────────────────────────────────────────────────────────

def send_shift_payment_caregiver_email(caregiver, shift) -> bool:
    content = f"""
    <h2>New Shift Confirmed — #{shift.pk}</h2>
    <p>Hi {caregiver.first_name or caregiver.username}, great news! An employer has paid and confirmed your upcoming shift.</p>
    <div class="info-box">
      <p><strong>Shift #:</strong> {shift.pk}</p>
      <p><strong>Employer:</strong> {shift.employer.get_full_name()}</p>
      <p><strong>Date:</strong> {shift.start_date.strftime('%B %d, %Y')}</p>
      <p><strong>Start time:</strong> {shift.start_time.strftime('%I:%M %p')}</p>
      <p><strong>Duration:</strong> {shift.duration_hours} hrs</p>
      <p><strong>Your rate:</strong> ${shift.hourly_rate}/hr</p>
      <p><strong>Your expected earnings:</strong>
         <strong>${round(float(shift.duration_hours or 0) * float(shift.hourly_rate) * 0.85, 2)} CAD</strong>
         (85% of total)</p>
      <p><strong>Location:</strong> {shift.city or 'Ontario'}</p>
    </div>
    <p>Please make sure to clock in when you arrive using the platform.
       If you have any questions, contact us at
       <a href="mailto:{ADMIN_EMAIL}">{ADMIN_EMAIL}</a>.</p>
    <a class="btn" href="{SITE_URL}/caregiver/dashboard/">View My Dashboard</a>
    """
    return send_transactional_email(
        subject=f'[{SITE_NAME}] Shift #{shift.pk} confirmed — you have a new booking',
        to_email=caregiver.email,
        html_body=_wrap(content),
    )


# ──────────────────────────────────────────────────────────────
# 6. Offline chat notification
# ──────────────────────────────────────────────────────────────

def send_offline_chat_notification(recipient, sender, message_body: str, conversation_id: int) -> bool:
    """Notify a user who is not online that they have received a new message."""
    preview = message_body[:120] + ('…' if len(message_body) > 120 else '')
    chat_url = f'{SITE_URL}/chatbot/messages/{conversation_id}/'

    content = f"""
    <h2>You have a new message</h2>
    <p>Hi {recipient.first_name or recipient.username},
       <strong>{sender.get_full_name() or sender.username}</strong>
       sent you a message on {SITE_NAME}:</p>
    <div class="info-box">
      <p><em>"{preview}"</em></p>
    </div>
    <p>Log in to reply:</p>
    <a class="btn" href="{chat_url}">Open Conversation</a>
    <p style="margin-top:20px; font-size:13px; color:#888;">
      You are receiving this because you were offline when the message was sent.
      To stop these notifications, simply stay logged in while chatting.
    </p>
    """
    return send_transactional_email(
        subject=f'[{SITE_NAME}] New message from {sender.get_full_name() or sender.username}',
        to_email=recipient.email,
        html_body=_wrap(content),
    )


# ──────────────────────────────────────────────────────────────
# 7. Employer account activation confirmation
#    (fired after Fincra activation payment is confirmed)
# ──────────────────────────────────────────────────────────────

def send_activation_confirmation_email(employer, payment) -> bool:
    dashboard_url = f'{SITE_URL}/employer/dashboard/'

    content = f"""
    <h2>Your account is now active!</h2>
    <p>Hi {employer.first_name or employer.username}, congratulations — your
       {SITE_NAME} employer account has been activated.</p>
    <div class="info-box">
      <p><strong>Account:</strong> {employer.get_full_name()}</p>
      <p><strong>Email:</strong> {employer.email}</p>
      <p><strong>Activation fee paid:</strong> ${payment.amount} CAD</p>
      <p><strong>Payment reference:</strong> {payment.payment_reference}</p>
      <p><strong>Activated on:</strong>
         {timezone.localtime(timezone.now()).strftime('%B %d, %Y at %I:%M %p')}</p>
    </div>
    <p>You can now:</p>
    <ul style="padding-left:20px;line-height:2;">
      <li>Post job offers and browse verified caregivers</li>
      <li>Negotiate rates directly via the in-platform chat</li>
      <li>Book and pay for caregiver shifts</li>
    </ul>
    <a class="btn" href="{dashboard_url}">Go to My Dashboard</a>
    <p style="margin-top:24px;">Questions? Contact us at
       <a href="mailto:{ADMIN_EMAIL}">{ADMIN_EMAIL}</a>.</p>
    """
    return send_transactional_email(
        subject=f'[{SITE_NAME}] Account activated — welcome aboard!',
        to_email=employer.email,
        html_body=_wrap(content),
    )


# ──────────────────────────────────────────────────────────────
# 8. Support chat resolved  (fired when admin marks chat resolved)
# ──────────────────────────────────────────────────────────────

def send_support_resolved_email(user, chat) -> bool:
    content = f"""
    <h2>Your support request has been resolved</h2>
    <p>Hi {user.first_name or user.username}, we are happy to let you know that
       your support chat (#{chat.pk}) has been marked as resolved by our team.</p>
    <div class="info-box">
      <p><strong>Support Chat #:</strong> {chat.pk}</p>
      <p><strong>Opened on:</strong> {chat.created_at.strftime('%B %d, %Y')}</p>
      <p><strong>Resolved on:</strong>
         {timezone.localtime(timezone.now()).strftime('%B %d, %Y at %I:%M %p')}</p>
    </div>
    <p>If your issue was not fully addressed or if you have further questions,
       please open a new support chat from your dashboard or contact us directly at
       <a href="mailto:{ADMIN_EMAIL}">{ADMIN_EMAIL}</a>.</p>
    <a class="btn" href="{SITE_URL}/chatbot/support/">Open Support Chat</a>
    """
    return send_transactional_email(
        subject=f'[{SITE_NAME}] Your support request has been resolved',
        to_email=user.email,
        html_body=_wrap(content),
    )


# ──────────────────────────────────────────────────────────────
# 9. Support chat offline notification
#    (fired when a support message arrives and the recipient is offline)
# ──────────────────────────────────────────────────────────────

def send_support_offline_notification(recipient, sender, message_body: str, chat_id: int, is_admin: bool = False) -> bool:
    """Notify offline user or admin of a new support message."""
    preview  = message_body[:120] + ('…' if len(message_body) > 120 else '')
    chat_url = (
        f'{SITE_URL}/chatbot/admin/support/{chat_id}/'
        if is_admin else
        f'{SITE_URL}/chatbot/support/{chat_id}/'
    )

    if is_admin:
        subject_line = f'[{SITE_NAME}] New support message from {sender.get_full_name() or sender.username}'
        heading      = 'New support message received'
        intro        = (
            f'<strong>{sender.get_full_name() or sender.username}</strong> '
            f'sent a new support message:'
        )
    else:
        subject_line = f'[{SITE_NAME}] Our team has replied to your support request'
        heading      = 'You have a reply from support'
        intro        = f'Our support team sent you a message:'

    content = f"""
    <h2>{heading}</h2>
    <p>Hi {recipient.first_name or recipient.username}, {intro}</p>
    <div class="info-box">
      <p><em>"{preview}"</em></p>
    </div>
    <a class="btn" href="{chat_url}">View Support Chat</a>
    <p style="margin-top:20px; font-size:13px; color:#888;">
      You received this because you were offline when the message was sent.
    </p>
    """
    return send_transactional_email(
        subject=subject_line,
        to_email=recipient.email,
        html_body=_wrap(content),
    )


# ──────────────────────────────────────────────────────────────
# 10. Caregiver payout notification
#     (fired when admin marks a ShiftLog as paid)
# ──────────────────────────────────────────────────────────────

def send_payout_notification_email(caregiver, log) -> bool:
    shift    = log.shift
    paid_str = timezone.localtime(timezone.now()).strftime('%B %d, %Y at %I:%M %p')

    content = f"""
    <h2>Your payment has been sent!</h2>
    <p>Hi {caregiver.first_name or caregiver.username}, great news — the admin has
       processed your payout for Shift #{shift.pk}.</p>
    <div class="info-box">
      <p><strong>Shift #:</strong> {shift.pk}</p>
      <p><strong>Date worked:</strong> {shift.start_date.strftime('%B %d, %Y')}</p>
      <p><strong>Hours worked:</strong> {log.hours_worked} hrs</p>
      <p><strong>Amount sent:</strong> <strong style="color:#1a6b4a;">${log.amount_earned} CAD</strong></p>
      <p><strong>Payment processed on:</strong> {paid_str}</p>
    </div>
    <p>Please allow 1–3 business days for the funds to appear in your account,
       depending on your bank. If you have any questions, contact us at
       <a href="mailto:{ADMIN_EMAIL}">{ADMIN_EMAIL}</a>.</p>
    <a class="btn" href="{SITE_URL}/caregiver/dashboard/">View My Dashboard</a>
    """
    return send_transactional_email(
        subject=f'[{SITE_NAME}] Your payout of ${log.amount_earned} CAD has been sent',
        to_email=caregiver.email,
        html_body=_wrap(content),
    )


# ──────────────────────────────────────────────────────────────
# 11. Dispute submitted — notify admin
# ──────────────────────────────────────────────────────────────

def send_dispute_submitted_admin_email(dispute) -> bool:
    employer  = dispute.employer
    caregiver = dispute.caregiver
    shift     = dispute.shift
    admin_url = f'{SITE_URL}/admin-app/disputes/{dispute.pk}/'

    content = f"""
    <h2>New Complaint / Dispute Submitted — #{dispute.pk}</h2>
    <p>An employer has raised a dispute. Please review it promptly.</p>
    <div class="info-box">
      <p><strong>Dispute #:</strong> {dispute.pk}</p>
      <p><strong>Category:</strong> {dispute.get_category_display()}</p>
      <p><strong>Employer:</strong> {employer.get_full_name()} ({employer.email})</p>
      <p><strong>Caregiver:</strong> {caregiver.get_full_name()} ({caregiver.email})</p>
      {'<p><strong>Shift #:</strong> ' + str(shift.pk) + ' (' + shift.start_date.strftime('%B %d, %Y') + ')</p>' if shift else ''}
      <p><strong>Description:</strong><br />{dispute.description}</p>
      <p><strong>Submitted on:</strong>
         {timezone.localtime(dispute.created_at).strftime('%B %d, %Y at %I:%M %p')}</p>
    </div>
    <a class="btn" href="{admin_url}">Review Dispute</a>
    """
    return send_transactional_email(
        subject=f'[Admin] New dispute #{dispute.pk} — {dispute.get_category_display()} — action required',
        to_email=ADMIN_EMAIL,
        html_body=_wrap(content),
    )


# ──────────────────────────────────────────────────────────────
# 12. Dispute resolved — notify employer
# ──────────────────────────────────────────────────────────────

def send_dispute_resolved_employer_email(dispute) -> bool:
    employer     = dispute.employer
    resolved_str = (
        timezone.localtime(dispute.resolved_at).strftime('%B %d, %Y at %I:%M %p')
        if dispute.resolved_at else 'N/A'
    )
    disputes_url = f'{SITE_URL}/employer/disputes/'

    content = f"""
    <h2>Your Dispute Has Been Resolved — #{dispute.pk}</h2>
    <p>Hi {employer.first_name or employer.username}, our team has reviewed and
       updated the status of your dispute.</p>
    <div class="info-box">
      <p><strong>Dispute #:</strong> {dispute.pk}</p>
      <p><strong>Category:</strong> {dispute.get_category_display()}</p>
      <p><strong>Status:</strong> <strong>{dispute.get_status_display()}</strong></p>
      <p><strong>Resolved on:</strong> {resolved_str}</p>
      {('<p><strong>Admin note:</strong><br />' + dispute.admin_note + '</p>') if dispute.admin_note else ''}
    </div>
    <p>If you have further concerns or the issue has not been fully addressed,
       please contact us at <a href="mailto:{ADMIN_EMAIL}">{ADMIN_EMAIL}</a>.</p>
    <a class="btn" href="{disputes_url}">View My Disputes</a>
    """
    return send_transactional_email(
        subject=f'[{SITE_NAME}] Dispute #{dispute.pk} has been {dispute.get_status_display().lower()}',
        to_email=employer.email,
        html_body=_wrap(content),
    )


# ──────────────────────────────────────────────────────────────
# 13. Job posted — broadcast to all active caregivers
#     (fired when an employer saves a new JobPosting)
# ──────────────────────────────────────────────────────────────

def send_job_posted_caregivers_email(job) -> int:
    """
    Send a job-alert email to every active, verified caregiver.
    Returns the number of emails successfully sent.
    """
    from Account.models import CaregiverProfile  # local import to avoid circular deps

    employer      = job.employer
    jobs_url      = f'{SITE_URL}/caregiver/browse-jobs/'
    care_type_label = job.get_care_type_display() if hasattr(job, 'get_care_type_display') else (job.care_type or 'Not specified')

    content_template = """
    <h2>New job opportunity — {title}</h2>
    <p>Hi {{name}}, a new job has just been posted on {site} that may match your profile.</p>
    <div class="info-box">
      <p><strong>Job title:</strong> {title}</p>
      <p><strong>Care type:</strong> {care_type}</p>
      <p><strong>Location:</strong> {city}</p>
      <p><strong>Schedule:</strong> {schedule}</p>
      {rate_line}
      <p><strong>Posted by:</strong> {employer_name}</p>
    </div>
    <p>Log in to your caregiver dashboard to view full details and apply directly.</p>
    <a class="btn" href="{jobs_url}">View Job</a>
    <p style="margin-top:20px; font-size:13px; color:#888;">
      You received this alert because you are a verified caregiver on {site}.
    </p>
    """.format(
        title        = job.title,
        site         = SITE_NAME,
        care_type    = care_type_label,
        city         = getattr(job, 'city', '') or getattr(job, 'location', '') or 'Ontario',
        schedule     = getattr(job, 'schedule', '') or 'Flexible',
        rate_line    = (
            f'<p><strong>Rate:</strong> ${job.hourly_rate}/hr</p>'
            if getattr(job, 'hourly_rate', None) else ''
        ),
        employer_name = employer.get_full_name() or employer.username,
        jobs_url      = jobs_url,
    )

    # Fetch all active caregivers who have an email address
    active_profiles = CaregiverProfile.objects.filter(
        status=CaregiverProfile.STATUS_ACTIVE
    ).select_related('user').exclude(user__email='')

    sent_count = 0
    for profile in active_profiles:
        user = profile.user
        if not user.email:
            continue
        personalised = content_template.replace(
            '{name}',
            user.first_name or user.username,
        )
        ok = send_transactional_email(
            subject   = f'[{SITE_NAME}] New job: {job.title} — Apply now',
            to_email  = user.email,
            html_body = _wrap(personalised),
        )
        if ok:
            sent_count += 1

    logger.info('Job-post broadcast: sent=%d for job_pk=%s', sent_count, job.pk)
    return sent_count


# ──────────────────────────────────────────────────────────────
# 14. Document upload reminder  (every 2 days until all 5 uploaded)
# ──────────────────────────────────────────────────────────────

def send_document_reminder_email(user, uploaded_count: int, required_count: int) -> bool:
    docs_url    = f'{SITE_URL}/caregiver/documents/'
    remaining   = required_count - uploaded_count

    content = f"""
    <h2>Don't forget — upload your documents</h2>
    <p>Hi {user.first_name or user.username}, your GetMeCare Ontario caregiver account
       is almost ready, but you still have <strong>{remaining} required document(s)</strong>
       to upload before your profile can be verified.</p>
    <div class="info-box">
      <p><strong>Documents uploaded:</strong> {uploaded_count} of {required_count}</p>
      <p><strong>Still needed:</strong> {remaining} document(s)</p>
    </div>
    <p>Required documents:</p>
    <ul style="padding-left:20px;line-height:2.2;font-size:14px;">
      <li>PSW Certificate</li>
      <li>Vulnerable Sector Check</li>
      <li>Government-issued ID</li>
      <li>First Aid / CPR Certificate</li>
      <li>Resume / CV</li>
    </ul>
    <p>Once all documents are uploaded and approved by our team, your profile will be
       activated and you'll start receiving shift offers from employers.</p>
    <a class="btn" href="{docs_url}">Upload Documents Now</a>
    <p style="margin-top:20px; font-size:13px; color:#888;">
      You're receiving this reminder because your document submission is incomplete.
      Contact us at <a href="mailto:{ADMIN_EMAIL}">{ADMIN_EMAIL}</a> if you need help.
    </p>
    """
    return send_transactional_email(
        subject=f'[{SITE_NAME}] Action required — {remaining} document(s) still needed',
        to_email=user.email,
        html_body=_wrap(content),
    )


# ──────────────────────────────────────────────────────────────
# 15. Profile completion reminder  (every 2 days until complete)
# ──────────────────────────────────────────────────────────────

def send_profile_reminder_email(user, missing_fields: list[str]) -> bool:
    profile_url = f'{SITE_URL}/edit-profile/'

    missing_html = ''.join(f'<li>{f}</li>' for f in missing_fields)

    content = f"""
    <h2>Complete your caregiver profile</h2>
    <p>Hi {user.first_name or user.username}, employers on {SITE_NAME} look at
       your profile before reaching out. A complete profile significantly increases
       your chances of getting booked for shifts.</p>
    <div class="info-box">
      <p><strong>Missing information:</strong></p>
      <ul style="padding-left:20px;line-height:2;margin-top:6px;">
        {missing_html}
      </ul>
    </div>
    <p>It only takes a few minutes to fill in the missing details.</p>
    <a class="btn" href="{profile_url}">Complete My Profile</a>
    <p style="margin-top:20px; font-size:13px; color:#888;">
      You're receiving this reminder because your caregiver profile is incomplete.
      Contact us at <a href="mailto:{ADMIN_EMAIL}">{ADMIN_EMAIL}</a> if you need help.
    </p>
    """
    return send_transactional_email(
        subject=f'[{SITE_NAME}] Your profile is incomplete — employers are waiting',
        to_email=user.email,
        html_body=_wrap(content),
    )


# ──────────────────────────────────────────────────────────────
# 16. Employer activation reminder  (every 2 days while inactive)
# ──────────────────────────────────────────────────────────────

def send_employer_activation_reminder_email(employer) -> bool:
    activate_url  = f'{SITE_URL}/employer/activate/'
    activation_fee = '49.99'   # mirrors EmployerProfile.ACTIVATION_FEE

    content = f"""
    <h2>Your employer account is not yet activated</h2>
    <p>Hi {employer.first_name or employer.username}, you signed up on {SITE_NAME}
       but your account is still <strong>inactive</strong>.</p>
    <p>Without activating, you cannot:</p>
    <ul style="padding-left:20px;line-height:2.2;font-size:14px;">
      <li>Post job offers visible to verified caregivers</li>
      <li>Book a caregiver for a shift</li>
      <li>Send direct messages to caregivers</li>
    </ul>
    <div class="info-box">
      <p><strong>One-time activation fee:</strong>
         <strong style="color:#1a6b4a;">${activation_fee} CAD</strong></p>
      <p>This is a single payment — no monthly subscription. Once activated,
         your account remains active permanently.</p>
    </div>
    <a class="btn" href="{activate_url}">Activate My Account Now</a>
    <p style="margin-top:20px; font-size:13px; color:#888;">
      You're receiving this reminder because your account has not been activated yet.
      Questions? Contact us at <a href="mailto:{ADMIN_EMAIL}">{ADMIN_EMAIL}</a>.
    </p>
    """
    return send_transactional_email(
        subject=f'[{SITE_NAME}] Activate your account to start hiring caregivers',
        to_email=employer.email,
        html_body=_wrap(content),
    )


# ──────────────────────────────────────────────────────────────
# 17. Document rejected — notify caregiver to re-upload
# ──────────────────────────────────────────────────────────────

def send_document_rejected_email(user, doc) -> bool:
    """
    Notify a caregiver that a specific document was rejected by the admin
    and ask them to re-upload it.
    """
    docs_url    = f'{SITE_URL}/caregiver/documents/'
    doc_label   = doc.get_doc_type_display()
    admin_note  = doc.note.strip() if doc.note else ''

    content = f"""
    <h2>Document rejected — action required</h2>
    <p>Hi {user.first_name or user.username}, our admin team has reviewed one of
       your uploaded documents and it could not be approved.</p>
    <div class="info-box">
      <p><strong>Document:</strong> {doc_label}</p>
      <p><strong>Status:</strong> <span style="color:#c62828;font-weight:700;">Rejected</span></p>
      {('<p><strong>Reason:</strong> ' + admin_note + '</p>') if admin_note else ''}
    </div>
    <p>Please re-upload a valid copy of your <strong>{doc_label}</strong> as soon as
       possible. Your profile cannot be fully verified until all required documents
       are approved.</p>
    <a class="btn" href="{docs_url}">Re-upload Document</a>
    <p style="margin-top:20px;">If you have questions about why your document was
       rejected or need guidance on what is accepted, please contact us at
       <a href="mailto:{ADMIN_EMAIL}">{ADMIN_EMAIL}</a>.</p>
    """
    return send_transactional_email(
        subject=f'[{SITE_NAME}] Your {doc_label} was rejected — please re-upload',
        to_email=user.email,
        html_body=_wrap(content),
    )


# ──────────────────────────────────────────────────────────────
# 18. Password changed successfully
#     (fired after a user successfully resets their password)
# ──────────────────────────────────────────────────────────────

def send_password_changed_email(user) -> bool:
    login_url = f'{SITE_URL}/login/'

    content = f"""
    <h2>Your password has been changed</h2>
    <p>Hi {user.first_name or user.username}, this is a confirmation that your
       {SITE_NAME} password was changed successfully.</p>
    <div class="info-box">
      <p><strong>Account:</strong> {user.get_full_name() or user.username}</p>
      <p><strong>Email:</strong> {user.email}</p>
      <p><strong>Changed on:</strong>
         {timezone.localtime(timezone.now()).strftime('%B %d, %Y at %I:%M %p')}</p>
    </div>
    <p>If you made this change, no further action is needed.</p>
    <p>If you did <strong>not</strong> change your password, your account may have been
       compromised. Please contact us immediately at
       <a href="mailto:{ADMIN_EMAIL}">{ADMIN_EMAIL}</a> and reset your password again.</p>
    <a class="btn" href="{login_url}">Sign In</a>
    """
    return send_transactional_email(
        subject=f'[{SITE_NAME}] Your password has been changed',
        to_email=user.email,
        html_body=_wrap(content),
    )
