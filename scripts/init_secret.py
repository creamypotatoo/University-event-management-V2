"""Initialize a private local session secret without displaying it."""
from pathlib import Path
import secrets
from dotenv import dotenv_values


def main():
    root=Path(__file__).resolve().parents[1]
    path=root/'.env'
    if not path.exists():
        path.write_text((root/'.env.example').read_text(encoding='utf-8'),encoding='utf-8')
    existing=dotenv_values(path).get('SECRET_KEY')
    if existing:
        if len(existing)<32:
            raise SystemExit('Existing SECRET_KEY is too short. Configure a private random key of at least 32 characters locally.')
        print('Existing session secret preserved; no value displayed.')
        return
    with path.open('a',encoding='utf-8') as stream:
        stream.write('\nSECRET_KEY='+secrets.token_hex(32)+'\n')
    print('New private session secret saved in the project .env; no value displayed.')


if __name__=='__main__':
    main()
