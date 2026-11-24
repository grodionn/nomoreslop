#!/usr/bin/env python3
"""Font discovery routes, bounded Fontsource metadata and optional local cmap audit.

No installation, arbitrary URLs, font execution, aesthetic grade or license approval.
Only --cache writes a new explicitly named file. inspect needs optional fontTools.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
import unicodedata
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler

ROOT = Path(__file__).resolve().parents[1]
MAX_JSON = 16 * 1024 * 1024
LIMIT = "Metadata/cmap evidence only; not proof of license, shaping, actual browser use, language completeness or design suitability."

def stamp(): return datetime.now(timezone.utc).isoformat(timespec='seconds')

def read_json(path):
    if path.stat().st_size > MAX_JSON: raise ValueError('JSON exceeds 16 MiB limit')
    return json.loads(path.read_text(encoding='utf-8-sig'))

def routes(script=None, role=None):
    data = read_json(ROOT / 'references/font-sources.json')
    sources = data['sources']
    script_routes = {'Jpan':{'Jpan','Hani','Hira','Kana'}, 'Kore':{'Kore','Hani','Hang'}, 'Hans':{'Hans','Hani'}, 'Hant':{'Hant','Hani'}}.get(script,{script}) if script else set()
    if script: sources = [item for item in sources if script_routes.intersection(item['scripts']) or '*' in item['scripts']]
    if role: sources = [item for item in sources if role in item['roles']]
    return {'sources': sources, 'count': len(sources), 'requested_script':script, 'discovery_script_routes':sorted(script_routes), 'checked_at': data.get('checked_at'), 'note': 'Local route filter, not live font search; script lists describe discovery scope, not every family. Composite CJK routing does not choose a locale or certify regional glyphs.'}

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs): return None

def get_metadata(url):
    request = Request(url, headers={'Accept':'application/json', 'User-Agent':'nomoreslop-font-research/18'})
    try:
        with build_opener(NoRedirect()).open(request, timeout=25) as response:
            raw = response.read(MAX_JSON + 1)
            if len(raw) > MAX_JSON: raise ValueError('Response exceeds 16 MiB limit')
            data = json.loads(raw.decode('utf-8-sig'))
    except HTTPError as error:
        return {'status':'unavailable', 'http_status':error.code, 'url':url, 'checked_at':stamp(), 'retry_after':error.headers.get('Retry-After'), 'note':'No automatic retry, alternate-interface access bypass or browser fallback.'}
    except (URLError, TimeoutError) as error:
        return {'status':'unavailable', 'url':url, 'checked_at':stamp(), 'error':str(error.reason if isinstance(error, URLError) else error)}
    return {'status':'received_metadata', 'url':url, 'checked_at':stamp(), 'response_sha256':hashlib.sha256(raw).hexdigest(), 'data':data}

def filter_rows(rows, subsets=(), category=None, weights=(), styles=(), variable=False):
    if not isinstance(rows, list) or not all(isinstance(row, dict) and isinstance(row.get('id'), str) for row in rows):
        raise ValueError('Expected a Fontsource font-object array, not a shell or unrelated JSON')
    result=[]
    for row in rows:
        if not set(subsets).issubset(row.get('subsets', [])): continue
        if category and row.get('category') != category: continue
        if not set(weights).issubset(row.get('weights', [])): continue
        if not set(styles).issubset(row.get('styles', [])): continue
        if variable and row.get('variable') is not True: continue
        result.append(row)
    return sorted(result, key=lambda row: row['id'])

def search(args):
    if args.cache and args.cache.exists(): raise ValueError('Cache already exists; no overwrite')
    query={}
    for key,value in [('subsets',args.subset),('weights',args.weight),('styles',args.style)]:
        if value: query[key]=','.join(map(str,value))
    if args.category: query['category']=args.category
    if args.variable: query['variable']='true'
    url='https://api.fontsource.org/v1/fonts'+('?' + urlencode(query) if query else '')
    if args.input:
        loaded=read_json(args.input)
        payload=loaded if isinstance(loaded, dict) and 'data' in loaded else {'data':loaded, 'status':'local_metadata'}
        mode='cached'; payload=dict(payload, cache_path=str(args.input))
    else:
        payload=get_metadata(url); mode='live'
        if payload['status']=='unavailable': return dict(payload, limitation=LIMIT)
    rows=filter_rows(payload.get('data'),args.subset,args.category,args.weight,args.style,args.variable)
    if args.cache:
        args.cache.parent.mkdir(parents=True,exist_ok=True)
        with args.cache.open('x',encoding='utf-8',newline='\n') as handle: json.dump(payload,handle,ensure_ascii=False,indent=2)
    start=(args.page-1)*args.page_size
    if args.page>1 and start>=len(rows): raise ValueError('Page is outside the filtered result')
    return {'status':'metadata_only','mode':mode,'source_url':payload.get('url'), 'checked_at':payload.get('checked_at'),
            'filters':query,'total':len(rows),'page':args.page,'page_size':args.page_size,'items':rows[start:start+args.page_size],
            'has_more':start+args.page_size<len(rows),'next_page':args.page+1 if start+args.page_size<len(rows) else None,
            'note':'ID ordering is pagination, not recommendation. Compare script/role/morphology before selection. Cached data is not a fresh request.', 'limitation':LIMIT}

def inspect_font(path, text, font_index=None):
    if not path.is_file() or path.stat().st_size>128*1024*1024: raise ValueError('Font must be an existing file of at most 128 MiB')
    try: from fontTools.ttLib import TTFont
    except ImportError:
        return {'status':'dependency_unavailable','reason':'Optional fontTools is unavailable; use an existing authorized environment or manual file inspection. No automatic install performed.', 'limitation':LIMIT}
    options={'lazy':True,'recalcBBoxes':False,'recalcTimestamp':False}
    if font_index is not None: options['fontNumber']=font_index
    try:
        with path.open('rb') as stream:
            with TTFont(stream,**options) as font:
                cmap=font.getBestCmap() or {}
                def sequence_control(cp):
                    return unicodedata.category(chr(cp)) in {'Cc','Cf'} or cp==0x034F or 0x180B<=cp<=0x180D or cp==0x180F or 0xFE00<=cp<=0xFE0F or 0xE0100<=cp<=0xE01EF
                required={ord(char) for char in text if not char.isspace() and not sequence_control(ord(char))}
                missing=[cp for cp in sorted(required) if cp not in cmap or cmap[cp]=='.notdef' or font.getGlyphID(cmap[cp])==0]
                ignored=[cp for cp in sorted(set(map(ord,text))) if sequence_control(cp)]
                names={}
                if 'name' in font:
                    for label,num in [('family',1),('subfamily',2),('typographic_family',16),('version',5),('license_metadata',13),('license_url_metadata',14)]:
                        names[label]=sorted({entry.toUnicode()[:1500] for entry in font['name'].names if entry.nameID==num})
                axes=[{'tag':axis.axisTag,'min':axis.minValue,'default':axis.defaultValue,'max':axis.maxValue} for axis in font['fvar'].axes] if 'fvar' in font else []
                shaping={tag: 'present' if tag in font else 'absent' for tag in ('GSUB','GPOS')}
                return {'status':'missing_characters' if missing else 'cmap_only','path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                        'font_index':font_index,'names':names,'axes':axes,'shaping_tables':shaping,'required_unique':len(required),
                        'missing':[{'codepoint':f'U+{cp:04X}','character':chr(cp),'name':unicodedata.name(chr(cp),'UNNAMED')} for cp in missing],
                        'format_controls_not_cmap_tested':[f'U+{cp:04X}' for cp in ignored],
                        'note':'Controls such as ZWJ/ZWNJ/variation selectors need sequence/shaping tests; table presence and cmap completeness do not prove correct shaping. License strings are metadata, not an approval.', 'limitation':LIMIT}
    except Exception as error:
        return {'status':'inspection_failed','error':str(error),'note':'For TTC/OTC provide an explicit --font-index; WOFF2 may require optional brotli.', 'limitation':LIMIT}

def main():
    # JSON output is UTF-8 even when a Windows terminal/pipe defaults to cp1252.
    for stream in (sys.stdout,sys.stderr):
        if hasattr(stream,'reconfigure'): stream.reconfigure(encoding='utf-8')
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest='command',required=True)
    source=commands.add_parser('sources');source.add_argument('--script');source.add_argument('--role',choices=['body','display','ui','data','fallback'])
    find=commands.add_parser('search',help='Fontsource metadata, not font recommendation or a license check')
    find.add_argument('--subset',action='append',default=[]);find.add_argument('--category',choices=['serif','sans-serif','display','handwriting','monospace'])
    find.add_argument('--weight',type=int,action='append',default=[]);find.add_argument('--style',choices=['normal','italic'],action='append',default=[]);find.add_argument('--variable',action='store_true')
    find.add_argument('--input',type=Path);find.add_argument('--cache',type=Path);find.add_argument('--page',type=int,default=1);find.add_argument('--page-size',type=int,default=15)
    inspect=commands.add_parser('inspect');inspect.add_argument('font',type=Path);inspect.add_argument('--text-file',type=Path,required=True);inspect.add_argument('--font-index',type=int)
    args=parser.parse_args()
    try:
        if args.command=='sources':
            if args.script and not re.fullmatch(r'[A-Z][a-z]{3}',args.script): raise ValueError('Use canonical ISO 15924 script code, e.g. Cyrl, Arab, Deva, Hani')
            result=routes(args.script,args.role)
        elif args.command=='search':
            if args.page<1 or not 1<=args.page_size<=50: raise ValueError('Use page>=1 and page-size 1..50')
            if any(not re.fullmatch('[a-z0-9-]+',item) for item in args.subset): raise ValueError('Invalid documented subset slug')
            result=search(args)
        else:
            if args.text_file.stat().st_size>1024*1024: raise ValueError('Text exceeds 1 MiB limit')
            if args.font_index is not None and args.font_index<0: raise ValueError('font-index must be nonnegative')
            result=inspect_font(args.font,args.text_file.read_text(encoding='utf-8-sig'),args.font_index)
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 1 if result.get('status') in {'unavailable','missing_characters','dependency_unavailable','inspection_failed'} else 0
    except (OSError,ValueError,TypeError,KeyError) as error:
        print(json.dumps({'status':'invalid','error':str(error)},ensure_ascii=False));return 2

if __name__=='__main__': sys.exit(main())
