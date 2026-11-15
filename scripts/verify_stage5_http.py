"""Reuse the complete approved rollback-only workflow verifier with final evidence."""
from .verify_stage4_http import run

if __name__=='__main__':
    run(output_name='STAGE5_HTTP_VALIDATION.json')
