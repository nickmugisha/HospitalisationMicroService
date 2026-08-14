from pathlib import Path
p = Path(__file__).resolve().parents[1] / 'services' / 'auth' / 'rbac.py'
text = p.read_text(encoding='utf-8')
marker = '# PROJECTX LOT K CHATBOT RBAC PATCH'
if marker not in text:
    patch = """

# PROJECTX LOT K CHATBOT RBAC PATCH
PERMISSIONS['chatbot.ask'] = 'Utiliser assistant conversationnel securise'
for _projectx_role_code in ROLES:
    ROLE_PERMISSIONS.setdefault(_projectx_role_code, set()).add('chatbot.ask')
"""
    p.write_text(text + patch, encoding='utf-8')
print('AUTH RBAC CHATBOT PATCH OK')
