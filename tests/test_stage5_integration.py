import copy
import os
import uuid
import pytest
from app import demo_seed,sql
from scripts.verify_sql_demos import FILES,run_demo
from test_stage2_integration import pg

pytestmark=[pytest.mark.integration,pytest.mark.skipif(os.getenv('RUN_RAW_SQL_INTEGRATION')!='1',reason='Explicit PostgreSQL integration opt-in required.')]
PASSWORD='fictional testing passphrase'


@pytest.fixture
def isolated_seed(pg,monkeypatch):
    app,conn,tag=pg
    monkeypatch.setattr(demo_seed,'EMAILS',[f'qa{tag}{i}@example.invalid' for i in range(4)])
    monkeypatch.setattr(demo_seed,'CLUBS',[f'QA {tag} Robotics',f'QA {tag} Arts'])
    monkeypatch.setattr(demo_seed,'VENUES',[f'QA {tag} Hall',f'QA {tag} Studio'])
    monkeypatch.setattr(demo_seed,'STUDENT_NUMBERS',[f'QA{tag}-{i}' for i in range(3)])
    state={}
    monkeypatch.setattr(demo_seed,'read_manifest',lambda:copy.deepcopy(state.get('manifest')))
    monkeypatch.setattr(demo_seed,'write_manifest',lambda value:state.update(manifest=copy.deepcopy(value)))
    return app,conn,state


def test_rollback_seed_check_leaves_no_records(isolated_seed):
    app,conn,state=isolated_seed
    result=app.test_cli_runner().invoke(args=['seed-demo','--check'])
    assert result.exit_code==0 and 'rolled back' in result.output and not state
    assert conn.execute('SELECT count(*) AS n FROM public.users WHERE email=ANY(%s)',(demo_seed.EMAILS,)).fetchone()['n']==0


def test_seed_apply_idempotence_without_overwrites(isolated_seed):
    app,conn,state=isolated_seed
    with app.app_context():
        first,existing=demo_seed.seed(apply=True,password=PASSWORD)
        assert not existing and sum(len(rows) for rows in first['rows'].values())==32
        second,existing=demo_seed.seed(apply=True,password=PASSWORD)
        assert existing and second==first
        demo_seed.verify_existing(conn,second)
    assert state['manifest']['state']=='applied'
    assert PASSWORD not in str(state)


def test_reserved_label_collision_without_manifest_is_refused(isolated_seed):
    app,conn,state=isolated_seed
    sql.execute(conn,'auth.create_admin_user',('Fictional collision',demo_seed.EMAILS[0],'unusable-test-hash','club_admin'),one=True)
    with app.app_context(),pytest.raises(demo_seed.SeedConflict,match='already exist'):
        demo_seed.seed(apply=True,password=PASSWORD)
    assert not state
    assert conn.execute('SELECT count(*) AS n FROM public.users WHERE email=ANY(%s)',(demo_seed.EMAILS,)).fetchone()['n']==1


def test_changed_owned_record_refuses_reseed(isolated_seed):
    app,conn,state=isolated_seed
    with app.app_context():
        manifest,_=demo_seed.seed(apply=True,password=PASSWORD)
        xid=manifest['rows']['event_expenses'][0]['id']
        conn.execute('UPDATE public.event_expenses SET description=%s WHERE expense_id=%s',('Edited fictional expense',xid))
        with pytest.raises(demo_seed.SeedConflict,match='missing or changed'):demo_seed.seed(apply=True,password=PASSWORD)
    assert conn.execute('SELECT description FROM public.event_expenses WHERE expense_id=%s',(xid,)).fetchone()['description']=='Edited fictional expense'


def test_persistent_seed_requires_private_password(isolated_seed):
    app,conn,state=isolated_seed
    with app.app_context(),pytest.raises(demo_seed.SeedConflict,match='privately supplied'):
        demo_seed.seed(apply=True)
    assert not state


def test_cli_password_hidden_and_existing_seed_noop(isolated_seed):
    app,conn,state=isolated_seed
    first=app.test_cli_runner().invoke(args=['seed-demo','--apply'],input=f'y\n{PASSWORD}\n{PASSWORD}\n')
    assert first.exit_code==0 and PASSWORD not in first.output
    second=app.test_cli_runner().invoke(args=['seed-demo','--apply'],input='y\n')
    assert second.exit_code==0 and 'No records inserted' in second.output
    assert 'Private demo passphrase:' not in second.output


@pytest.mark.parametrize('path',FILES,ids=lambda path:path.name)
def test_safe_temporary_and_readonly_demonstrations(app,path):
    result=run_demo(app,path)
    assert result.returncode==0,result.stderr
    if path.name.startswith('01_'):assert result.stderr.count('PASS:')==6
    if path.name.startswith('03_'):assert '30.30' in result.stdout and '100.0' in result.stdout and '50.0' in result.stdout
