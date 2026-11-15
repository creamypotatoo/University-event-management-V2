"""Positive-list, secret-checked source submission ZIP. Never commits or publishes."""
from datetime import datetime
import hashlib
import json
from pathlib import Path
import zipfile
from dotenv import dotenv_values

ROOT=Path(__file__).resolve().parents[1]
FOLDERS=('app','scripts','sql','docs','tests')
ROOT_FILES=('README.md','.gitignore','.env.example','requirements.txt','requirements-dev.txt','requirements-lock.txt','pytest.ini','run.py')
EXCLUDED={'.git','.venv','.cache','.demo','__pycache__','.pytest_cache','submission'}


def safe_files():
    selected=[]
    for name in ROOT_FILES:
        path=ROOT/name
        if path.is_file():selected.append(path)
    for folder in FOLDERS:
        for path in (ROOT/folder).rglob('*'):
            relative=path.relative_to(ROOT)
            if not path.is_file() or any(part in EXCLUDED for part in relative.parts):continue
            if path.name.startswith('.env') or path.suffix in {'.pyc','.log'}:continue
            if not path.resolve().is_relative_to(ROOT.resolve()):raise RuntimeError('Refusing file outside project root')
            selected.append(path)
    for path in ROOT.glob('STAGE*'):
        if path.is_file() and path.suffix in {'.md','.json','.xml','.txt'}:selected.append(path)
    return sorted(set(selected),key=lambda path:str(path.relative_to(ROOT)))


def build():
    example=dotenv_values(ROOT/'.env.example')
    if any(example.get(name) for name in ('PGPASSWORD','SECRET_KEY','DEMO_PASSWORD')):raise RuntimeError('Example configuration must have blank secrets')
    private=dotenv_values(ROOT/'.env') if (ROOT/'.env').exists() else {}
    secrets=[value.encode() for name,value in private.items() if name in {'SECRET_KEY','DEMO_PASSWORD','PGPASSWORD'} and value and len(value)>=12]
    files=safe_files()
    for path in files:
        content=path.read_bytes()
        if any(value in content for value in secrets):raise RuntimeError('Private configured secret detected; refusing package without displaying it')
    manifest={'project':'University Event and Club Management - Raw SQL Edition','base_tables':9,'reporting_views':3,'exclusions':['.env','private manifests','.git','.venv','browser caches','logs'],'files':[{'path':path.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()} for path in files]}
    destination=ROOT/'submission';destination.mkdir(exist_ok=True)
    archive=destination/('university_events_raw_sql_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f')+'.zip')
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED) as output:
        for path in files:output.write(path,'university_events_raw_sql/'+path.relative_to(ROOT).as_posix())
        output.writestr('university_events_raw_sql/SUBMISSION_MANIFEST.json',json.dumps(manifest,indent=2))
    with zipfile.ZipFile(archive) as check:
        assert check.testzip() is None
        assert all('/.env' not in name or name.endswith('/.env.example') for name in check.namelist())
        assert not any(any(part in EXCLUDED for part in Path(name).parts) for name in check.namelist())
    evidence={'archive':archive.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'file_count':len(files)+1,'private_configuration_included':False,'git_repository_included':False,'manifest':manifest}
    (destination/'SUBMISSION_CONTENTS.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
    print('Created sanitized submission:',archive.relative_to(ROOT))
    print('Files:',len(files)+1,'| Private configuration, manifests, caches and Git excluded.')
    return archive


if __name__=='__main__':build()
