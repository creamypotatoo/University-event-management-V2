"""Execute safe educational TEMP/read-only scripts, never schema/seed scripts."""
import os
from pathlib import Path
import shutil
import subprocess
from app import create_app

ROOT=Path(__file__).resolve().parents[1]
FILES=sorted((ROOT/'sql/demo').glob('[0-9][0-9]_*.sql'))


def run_demo(app,path):
    path=path.resolve()
    if path not in [p.resolve() for p in FILES]:raise ValueError('Only reviewed sql/demo files are allowed.')
    c=app.config
    assert c['DB_NAME']=='university_events_raw'
    binary=shutil.which('psql') or r'C:\Program Files\PostgreSQL\18\bin\psql.exe'
    env=os.environ.copy();env['PGPASSWORD']=c['DB_PASSWORD']
    return subprocess.run([binary,'-X','-w','-h',c['DB_HOST'],'-p',str(c['DB_PORT']),'-U',c['DB_USER'],'-d','university_events_raw','-v','ON_ERROR_STOP=1','-f',str(path)],env=env,capture_output=True,text=True)


def main():
    app=create_app();outputs=[]
    for path in FILES:
        result=run_demo(app,path)
        if result.returncode:
            print('FAILED:',path.name)
            print(result.stderr[-1200:])
            raise SystemExit(1)
        print(path.name+': passed')
        outputs.append(path.name+'\n'+result.stdout+'\n'+result.stderr)
    (ROOT/'STAGE5_SQL_DEMO_OUTPUT.txt').write_text('\n'.join(outputs),encoding='utf-8')


if __name__=='__main__':main()
