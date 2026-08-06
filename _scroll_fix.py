SCROLLBAR_CSS = """
  /* scroll-table-wrap */
  .scroll-table-wrap{max-height:520px;overflow-y:auto;overflow-x:auto}
  .scroll-table-wrap::-webkit-scrollbar{width:5px;height:5px}
  .scroll-table-wrap::-webkit-scrollbar-track{background:#f2f4f0;border-radius:4px}
  .scroll-table-wrap::-webkit-scrollbar-thumb{background:#c8d8c8;border-radius:4px}
  .scroll-table-wrap::-webkit-scrollbar-thumb:hover{background:#1b7d4f}
"""

files = [
    r'c:\Users\ADMIN\Desktop\pyworkspace\NEW\templates\AdminApp\base_admin.html',
    r'c:\Users\ADMIN\Desktop\pyworkspace\NEW\templates\EmployerApp\base_employer.html',
    r'c:\Users\ADMIN\Desktop\pyworkspace\NEW\templates\CareGiverAcc\base_caregiver.html',
]

for path in files:
    with open(path, encoding='utf-8') as f:
        c = f.read()
    if 'scroll-table-wrap' in c:
        print('SKIP:', path)
        continue
    idx = c.find('</style>')
    if idx == -1:
        print('NO </style>:', path)
        continue
    c = c[:idx] + SCROLLBAR_CSS + c[idx:]
    with open(path, 'w', encoding='utf-8') as f:
        f.write(c)
    print('OK:', path)
