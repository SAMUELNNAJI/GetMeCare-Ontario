import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'GETMECARE.settings')
django.setup()
from django.template.base import Lexer, TokenType

with open('templates/EmployerApp/dashboard.html', 'r') as f:
    content = f.read()

lexer = Lexer(content)
tokens = list(lexer.tokenize())

block_tokens = []
for t in tokens:
    if t.token_type == TokenType.BLOCK:
        block_tokens.append((t.lineno, t.contents))

print(f"Total tokens: {len(tokens)}")
print(f"Block tokens: {len(block_tokens)}")
for lineno, contents in block_tokens:
    print(f"Line {lineno}: {contents}")
