path = r'c:\Users\ADMIN\Desktop\pyworkspace\NEW\templates\CareGiverAcc\documents.html'
with open(path, encoding='utf-8') as f:
    c = f.read()

print('btn-reupload-trigger found:', 'btn-reupload-trigger' in c)
print('reupload_document found:', 'reupload_document' in c)

idx = c.find('item.status')
print('item.status found at:', idx)
if idx != -1:
    print(repr(c[idx:idx+300]))
