import zipfile
with zipfile.ZipFile('auto_shutdown.zip', 'w') as zf:
    zf.write('auto_shutdown.py', 'index.py')
print('Created auto_shutdown.zip')