import logging
import sys

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class AccountConfig(AppConfig):
    name = 'Account'

    def ready(self):
        """Start the background scheduler when Django boots.

        The scheduler runs the send_reminder_emails management command
        every 2 days (48 hours).  It is started only in the main process
        (not in runserver's auto-reloader child, not during management
        commands like migrate/makemigrations, and not during tests) to
        prevent duplicate jobs.
        """
        # Skip during migrations, tests, and the reloader watchdog process
        _skip_commands = {
            'migrate', 'makemigrations', 'test',
            'collectstatic', 'shell', 'dbshell',
            'createsuperuser', 'send_reminder_emails',
        }
        argv = sys.argv
        if len(argv) > 1 and argv[1] in _skip_commands:
            return

        # The reloader spawns a child process with RUN_MAIN=true — only
        # start the scheduler in the child (the real server process).
        import os
        if os.environ.get('RUN_MAIN') == 'true' or not _is_runserver():
            _start_scheduler()


def _is_runserver() -> bool:
    """True when Django is running as a web server (runserver or gunicorn)."""
    argv = sys.argv
    if not argv:
        return False
    cmd = argv[1] if len(argv) > 1 else ''
    # gunicorn / uvicorn have no argv[1]; runserver does
    return cmd in ('runserver',) or 'gunicorn' in argv[0] or len(argv) == 1


def _start_scheduler():
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.interval import IntervalTrigger
        from django.core import management

        scheduler = BackgroundScheduler(timezone='America/Toronto')
        scheduler.add_job(
            func=_run_reminder_command,
            trigger=IntervalTrigger(hours=48),
            id='send_reminder_emails',
            name='Send every-2-day reminder emails to incomplete caregiver profiles',
            replace_existing=True,
            misfire_grace_time=3600,   # allow up to 1 hr late
        )
        scheduler.start()
        logger.info('[Scheduler] send_reminder_emails job started — runs every 48 h')
    except Exception:
        # Never crash Django startup because of the scheduler
        logger.exception('[Scheduler] Failed to start background scheduler')


def _run_reminder_command():
    """Wrapper called by APScheduler — runs the management command in-process."""
    try:
        from django.core import management
        management.call_command('send_reminder_emails', verbosity=0)
        logger.info('[Scheduler] send_reminder_emails completed')
    except Exception:
        logger.exception('[Scheduler] send_reminder_emails job failed')
