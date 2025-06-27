from django.core.mail.backends.smtp import EmailBackend
from django.core.mail import EmailMessage
from django.utils.html import strip_tags
import re
from apps.base.models import EmailConfig
import logging
import threading
logger = logging.getLogger(__name__)

class CustomEmailBackend:
    def __init__(self,request, subject='Testing mails', body="Hi, there is a system generated test mail. Ignore if you are reading this!", to=["titusowuor30@gmail.com"], attachments=None):
        self.request=request
        self.subject=subject
        self.body=body
        self.to=to
        self.attachments=attachments

    def send_email(self):
        try:
            logger.info(self.request.META['HTTP_HOST'])
            domain = self.request.META['HTTP_HOST']
            protocol = 'https' if self.request.is_secure() else 'http'
            site_login_url = str(protocol+'://'+str(domain).replace(str(domain).split(':')[1],'8080'))+"/login"
            config = EmailConfig.objects.first()
            logger.info(config)
            backend = EmailBackend(host=config.email_host, port=config.email_port, username=config.email_host_user,
                                password=config.email_host_password, use_tls=config.email_use_tls, fail_silently=config.fail_silently)
            # replace &nbsp; with space
            message = re.sub(r'(?<!&nbsp;)&nbsp;', ' ', strip_tags(self.body))
            message=message+f"\nDITS Portal url {site_login_url}"
            if self.attachments:
                logger.info('check attachments...')
                email = EmailMessage(
                    subject=self.subject, body=message, from_email=config.email_from, to=self.to, connection=backend)
                logger.info(email)
                for attch in self.attachments:
                    email.attach(attch.name, attch.read(),
                                attch.content_type)
                threading.Thread(target=email.send).start()
                logger.info('Email sent successfully!')
            else:
                email = EmailMessage(
                    subject=self.subject, body=message, from_email=config.email_from, to=self.to, connection=backend)
                threading.Thread(target=email.send).start()
                logger.info('Email sent successfully!')
        except Exception as e:
            logger.error(e)
            logger.error("Email send error:{}".format(e))