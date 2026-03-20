#!/usr/bin/env python3
"""Regenerate jobSites.json and tg_sources.json from sources.json."""
import json

SOURCES = '/home/oc/jora/scanner/config/sources.json'
JOBSITES = '/home/oc/jora/scanner/config/jobSites.json'
TG_SOURCES = '/home/oc/jora/scanner/config/tg_sources.json'

sources = json.load(open(SOURCES))

web = sorted(
    [{'name': s['name'], 'url': s['url'],
      'jobTitleSelector': s['config']['jobTitleSelector'],
      'antiBotCheck': s['config'].get('antiBotCheck', False),
      'scan_method': s['config'].get('scan_method', 'axios'),
      'priority': s.get('priority', 5)}
     for s in sources if s['type'] == 'web' and s['status'] == 'active'],
    key=lambda x: x['priority'], reverse=True
)

tg = [{'id': s['id'], 'type': 'telegram_public', 'name': s['name'],
       'channel': s.get('channel', ''), 'url': s['url'], 'status': 'active',
       'priority': s.get('priority', 5)}
      for s in sources if s['type'] == 'telegram' and s['status'] == 'active']

open(JOBSITES, 'w').write(json.dumps(web, indent=2, ensure_ascii=False))
open(TG_SOURCES, 'w').write(json.dumps(tg, indent=2, ensure_ascii=False))
print(f'Regenerated: {len(web)} web + {len(tg)} TG sources')
