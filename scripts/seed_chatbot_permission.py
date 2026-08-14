from sqlalchemy import select
from database.session import SessionLocal
from services.auth.models import Permission, Role
s=SessionLocal()
try:
    perm=s.scalar(select(Permission).where(Permission.code=='chatbot.ask'))
    if perm is None:
        perm=Permission(code='chatbot.ask',name='Utiliser assistant sécurisé',description='Utiliser le chatbot ProjectX selon les permissions métier existantes.')
        s.add(perm); s.flush()
    roles=s.scalars(select(Role).where(Role.active.is_(True))).all()
    for role in roles:
        if perm not in role.permissions: role.permissions.append(perm)
    s.commit(); print('CHATBOT PERMISSION SEEDED:',len(roles),'active role(s)')
except Exception:
    s.rollback(); raise
finally: s.close()
