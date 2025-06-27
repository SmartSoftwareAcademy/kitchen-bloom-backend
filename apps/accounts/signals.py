import logging
from django.contrib.sessions.models import Session
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import UserSession
from django.contrib.auth import get_user_model

User = get_user_model()
logger = logging.getLogger(__name__)


def register_signals():
    """Register all signal handlers."""
    post_save.connect(
        create_or_update_user_session,
        sender=Session,
        dispatch_uid='create_or_update_user_session'
    )


@receiver(post_save, sender=Session)
def create_or_update_user_session(sender, instance, created, **kwargs):
    """
    Signal handler to create or update user session in the database.
    """
    try:
        session_data = instance.get_decoded()
        user_id = session_data.get('_auth_user_id')
        
        if user_id:
            user = User.objects.get(id=user_id)
            
            # Get user agent and IP from session data if available
            user_agent = session_data.get('user_agent', '')
            ip_address = session_data.get('ip_address', '')
            
            UserSession.objects.update_or_create(
                session_key=instance.session_key,
                defaults={
                    'user': user,
                    'user_agent': user_agent,
                    'ip_address': ip_address,
                    'is_active': True
                }
            )
            
    except User.DoesNotExist:
        logger.warning(
            f"User with id {user_id} not found for session {instance.session_key}"
        )
    except Exception as e:
        logger.error(f"Error in create_or_update_user_session: {str(e)}", exc_info=True)