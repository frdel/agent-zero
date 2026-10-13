import html
import json
from pathlib import Path
import re
import shutil
import subprocess

import pytest


@pytest.mark.skipif(not shutil.which('node'), reason='node is required')
def test_model_search_discards_stale_requests_and_allows_fresh_search():
    source = (Path(__file__).parents[1] / 'plugins/_model_config/webui/model-field.html').read_text()
    controller = html.unescape(re.search(r'x-data="(\{ results: \[\], source:.*?})"', source, re.S).group(1))
    script = r'''
import assert from 'node:assert/strict';
for (const change of ['draft', 'provider', 'base']) {
  let model = {name:'first'}, _prov = 'openai', _apiBase = 'same';
  const searchType = 'chat';
  let requestedQuery;
  let resolve;
  const $store = {modelConfig:{searchModelsDetailed:(p, q) => { requestedQuery = q; return new Promise(r=>resolve=r); }}};
  const field = eval('(' + CONTROLLER + ')');
  field.doSearch();
  assert.equal(requestedQuery, '');
  if (change === 'draft') model = {name:'first'};
  if (change === 'provider') _prov = 'other';
  if (change === 'base') _apiBase = 'other';
  resolve({models:['stale'],source:'provider_endpoint'});
  await new Promise(setImmediate);
  assert.deepEqual(field.results, []);
  assert.equal(field.open, false);
  assert.equal(field.searching, false);
  field.doSearch();
  resolve({models:['fresh'],source:'provider_endpoint'});
  await new Promise(setImmediate);
  assert.deepEqual(field.results, ['fresh']);
  assert.equal(field.open, true);
  assert.equal(field.searching, false);
}
'''.replace('CONTROLLER', json.dumps(controller))
    subprocess.run(['node', '--input-type=module', '-e', script], check=True)
