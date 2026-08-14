from sqlalchemy import create_engine,event
from sqlalchemy.orm import sessionmaker
from services.maternite.config import DATABASE_URL
engine=create_engine(DATABASE_URL,pool_pre_ping=True,pool_recycle=1800)
@event.listens_for(engine,"connect")
def set_mysql_timezone(dbapi_connection,connection_record):
    cursor=dbapi_connection.cursor()
    try: cursor.execute("SET time_zone = '+00:00'")
    finally: cursor.close()
MaterniteSessionLocal=sessionmaker(bind=engine,autoflush=False,autocommit=False,expire_on_commit=False)
