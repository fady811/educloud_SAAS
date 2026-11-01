# ASGI entry point — NO Channels routing (CON-03, structural test REQ-COMM-03).
import os
from django.core.asgi import get_asgi_application
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")
application = get_asgi_application()
