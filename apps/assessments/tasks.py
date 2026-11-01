from celery import shared_task


@shared_task(queue="default")
def auto_submit_expired_attempts():
    from apps.assessments.services.attempts import auto_submit_expired
    return auto_submit_expired()
