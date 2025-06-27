# create middle to seed default email and sma configs
from django.utils.deprecation import MiddlewareMixin
from .models import EmailConfig, SMSSettings, SystemModuleSettings

class SeedDefaultConfigsMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if not EmailConfig.objects.exists():
            EmailConfig.objects.update_or_create(
                provider='smtp',
                email_host='smtp.gmail.com',
                email_port=587,
                email_host_user='codevertexitsolutions@gmail.com',
                email_host_password='fskwauczrnscjikr',
                email_use_tls=True,
                email_use_ssl=False,
                email_from='codevertexitsolutions@gmail.com',
                email_from_name='CodeVertex',
                email_subject='CodeVertex',
                email_body='CodeVertex',
            )
        if not SMSSettings.objects.exists():
            SMSSettings.objects.update_or_create(
                provider='twilio',
                twilio_account_sid='AC6c2c2c2c2c2c2c2c2c2c2c2c2c2c2c2c2',
                twilio_auth_token='fskwauczrnscjikr',
                twilio_phone_number='+1234567890',
                africastalking_username='fskwauczrnscjikr',
                africastalking_api_key='fskwauczrnscjikr',
                africastalking_sender_id='+254743793901',
                is_active=True,
            )
        # Auto-update SystemModuleSettings for key apps
        relevant_apps = ['sales', 'inventory', 'crm', 'tables','payroll','kds','employees']
        settings = SystemModuleSettings.get_solo()
        default_modules = SystemModuleSettings.getDefaultModules()
        modules_config = settings.modules_config or {}
        updated = False
        for app in relevant_apps:
            if app not in modules_config or not modules_config.get(app):
                modules_config[app] = default_modules.get(app, {})
                updated = True
        if updated:
            settings.modules_config = modules_config
            settings.save()

