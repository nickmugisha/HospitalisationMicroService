import logging
from sqlalchemy import text
from common.v1 import common_pb2
from services.common.health_compat import build_health_response_compat
from database.session import engine
from services.auth.service import AuthService
logger=logging.getLogger('projectx.auth.runtime')

def build_health(status,message):
    return build_health_response_compat("auth", status, message, "1.0.0")

class RuntimeAuthService(AuthService):
    def HealthCheck(self,request,context):
        try:
            with engine.connect() as c: c.execute(text('SELECT 1'))
            return build_health('ONLINE','Auth service and MySQL are available.')
        except Exception:
            logger.exception('Auth HealthCheck degraded')
            return build_health('DEGRADED','Auth service is running but MySQL is unavailable.')
