"""Static plot page smoke tests."""
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app


def test_plot_page_and_api(data_dir):
    client = TestClient(create_app())
    response = client.get('/app/plot2d/')
    assert response.status_code == 200
    assert response.headers['content-type'].startswith('text/html')
    for element_id in ('canvas', 'btn-demo', 'btn-optimize', 'score', 'status'):
        assert f'id="{element_id}"' in response.text
    for asset in ('plot.js', 'format.js', 'style.css'):
        assert client.get(f'/app/plot2d/{asset}').status_code == 200
    for target in re.findall(r'(?:src|href)="([^"]+)"', response.text):
        assert not target.startswith(('http://', 'https://', '//'))
    health = client.get('/health')
    assert health.status_code == 200
    assert health.headers['content-type'].startswith('application/json')
    assert health.json() == {'ok': True}


@pytest.mark.skipif(shutil.which('node') is None, reason='Node is not installed')
def test_format_helpers_in_node():
    module_uri = (Path(__file__).parents[2] / 'web' / 'plot2d' / 'format.js').as_uri()
    script = f"""
      import {{ readFileSync }} from 'node:fs';
      import assert from 'node:assert/strict';
      const source = readFileSync(new URL('{module_uri}'), 'utf8');
      const {{ formatFtIn, parseFtIn, objectSvgRotation }} = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));
      assert.equal(formatFtIn(7.5), '7\\' 6"');
      assert.equal(formatFtIn(3.6), '3\\' 7"');
      assert.equal(formatFtIn(0), '0\\' 0"');
      assert.equal(formatFtIn(11.99), '12\\' 0"');
      assert.equal(formatFtIn(-1.5), '-1\\' 6"');
      assert.equal(parseFtIn('7\\' 6"'), 7.5);
      assert.equal(objectSvgRotation(90), -90);
      assert.equal(objectSvgRotation(-45), 45);
    """
    subprocess.run(['node', '--input-type=module', '-e', script], check=True, capture_output=True, text=True)
