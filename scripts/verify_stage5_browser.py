"""Real offline desktop/mobile browser QA, no database record mutations."""
import json
import os
from pathlib import Path
import threading
from dotenv import dotenv_values
from playwright.sync_api import sync_playwright
from werkzeug.serving import make_server,WSGIRequestHandler
from app import create_app
from app.demo_seed import EMAILS

ROOT=Path(__file__).resolve().parents[1]

class QuietHandler(WSGIRequestHandler):
    def log_request(self,*args,**kwargs):pass


def run():
    os.environ.setdefault('PLAYWRIGHT_BROWSERS_PATH',str(ROOT/'.cache/ms-playwright'))
    password=dotenv_values(ROOT/'.env').get('DEMO_PASSWORD')
    if not password:raise SystemExit('Approved seeded demo accounts and private local DEMO_PASSWORD are required.')
    app=create_app();server=make_server('127.0.0.1',0,app,request_handler=QuietHandler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    base=f'http://127.0.0.1:{server.server_port}'
    folder=ROOT/'docs/screenshots';folder.mkdir(parents=True,exist_ok=True)
    evidence={'external_requests':[],'page_errors':[],'screenshots':[],'checks':[]}
    try:
        with sync_playwright() as playwright:
            browser=playwright.chromium.launch(headless=True)
            try:
                for label,viewport in [('desktop',{'width':1440,'height':1000}),('mobile',{'width':390,'height':844})]:
                    context=browser.new_context(viewport=viewport,locale='en-GB')
                    def allow(route):
                        if route.request.url.startswith(base+'/'):route.continue_()
                        else:
                            evidence['external_requests'].append(route.request.url);route.abort()
                    context.route('**/*',allow)
                    page=context.new_page()
                    page.on('pageerror',lambda error:evidence['page_errors'].append(str(error)))
                    def capture(name,path):
                        response=page.goto(base+path,wait_until='networkidle')
                        assert response.status==200
                        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth + 1'),f'Page overflow: {label}/{name}'
                        target=folder/f'{label}-{name}.png';page.screenshot(path=str(target),full_page=True)
                        evidence['screenshots'].append(str(target.relative_to(ROOT)))
                        evidence['checks'].append({'viewport':label,'page':path,'http':200,'horizontal_page_overflow':False})
                    capture('home','/');capture('events','/events');capture('clubs','/clubs')
                    page.goto(base+'/auth/login');page.locator('#email').fill(EMAILS[1]);page.locator('#password').fill(password)
                    page.get_by_role('button',name='Log in',exact=True).click();page.wait_for_url('**/dashboard/student')
                    capture('student-dashboard','/dashboard/student')
                    page.goto(base+'/profile/edit');page.locator('form[method="post"]').last.evaluate('(form)=>form.noValidate=true')
                    page.locator('#full_name').fill('');page.get_by_role('button',name='Save changes').click()
                    assert page.locator('#full_name').get_attribute('aria-invalid')=='true'
                    target=folder/f'{label}-validation.png';page.screenshot(path=str(target),full_page=True)
                    evidence['screenshots'].append(str(target.relative_to(ROOT)))
                    page.get_by_role('button',name='Log out',exact=True).click();page.wait_for_url('**/auth/login')
                    page.locator('#email').fill(EMAILS[0]);page.locator('#password').fill(password)
                    page.get_by_role('button',name='Log in',exact=True).click();page.wait_for_url('**/dashboard/club-admin')
                    capture('admin-dashboard','/dashboard/club-admin');capture('financial','/reports/financial');capture('participation','/reports/analytics')
                    context.close()
                assert not evidence['external_requests'] and not evidence['page_errors']
            finally:browser.close()
    finally:
        server.shutdown();thread.join(timeout=5);server.server_close()
    evidence['temporary_server_stopped']=True
    (ROOT/'STAGE5_BROWSER_VALIDATION.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
    print('Desktop/mobile browser QA passed; all assets local, no horizontal page overflow or page errors.')
    print('Sixteen screenshots saved without passwords. Temporary server stopped; no database records changed.')


if __name__=='__main__':run()
