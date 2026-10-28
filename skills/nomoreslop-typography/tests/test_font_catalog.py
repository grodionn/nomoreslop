import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import sys
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import unquote, urlsplit

SCRIPT=Path(__file__).resolve().parents[1]/'scripts/font_catalog.py'
SPEC=importlib.util.spec_from_file_location('font_catalog',SCRIPT)
fc=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(fc)
try:
    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    HAS_FONTTOOLS=True
except ImportError: HAS_FONTTOOLS=False

ROWS=[{'id':'zeta','family':'Zeta','subsets':['latin','cyrillic'],'weights':[400,700],'styles':['normal'],'category':'serif','variable':True},
      {'id':'alpha','family':'Alpha','subsets':['latin'],'weights':[400],'styles':['normal','italic'],'category':'serif','variable':False},
      {'id':'beta','family':'Beta','subsets':['latin','cyrillic'],'weights':[400],'styles':['normal'],'category':'sans-serif','variable':False}]

class FontCatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
    def tearDown(self): self.temp.cleanup()
    def cli(self,*args):
        with patch.object(sys,'argv',['font_catalog.py',*map(str,args)]),contextlib.redirect_stdout(io.StringIO()) as out:
            status=fc.main()
        return status,json.loads(out.getvalue())
    def cache(self):
        p=self.root/'metadata.json';p.write_text(json.dumps({'url':'https://api.fontsource.org/v1/fonts','checked_at':'fixture-not-live','data':ROWS}),encoding='utf-8');return p
    def test_script_routes_cover_discovery_not_per_font_guarantees(self):
        data=fc.routes('Arab','body');self.assertGreater(len(data['sources']),0)
        self.assertIn('not every family',data['note'])
        catalog=fc.routes();ids=[item['id'] for item in catalog['sources']]
        self.assertEqual(len(ids),len(set(ids)))
        self.assertTrue(all(item.get('license_evidence') and item.get('license_scope') and item.get('caveats') for item in catalog['sources']))
        source_map=fc.read_json(SCRIPT.parents[1]/'references/font-sources.json')
        self.assertEqual(source_map['schema_version'],1)
        for source in catalog['sources']:
            self.assertTrue(source['scripts'])
            self.assertTrue(all(tag=='*' or re.fullmatch(r'[A-Z][a-z]{3}',tag) for tag in source['scripts']))
            self.assertTrue(source['roles'])
            self.assertTrue(set(source['roles']).issubset({'body','display','ui','data','fallback'}))
            for value in [source['url'],*source['license_evidence']]:
                parsed=urlsplit(value)
                self.assertEqual(parsed.scheme,'https')
                self.assertTrue(parsed.hostname)
    def test_standalone_package_has_no_missing_or_foreign_local_reference(self):
        root=SCRIPT.parents[1].resolve()
        for document in root.rglob('*.md'):
            for value in re.findall(r'!?\[[^\]\n]*\]\((<?[^)\s]+>?)\)',document.read_text(encoding='utf-8')):
                parsed=urlsplit(value.strip('<>'))
                if parsed.scheme or not parsed.path: continue
                destination=(document.parent/unquote(parsed.path)).resolve()
                self.assertTrue(destination.is_relative_to(root),(document,value))
                self.assertTrue(destination.is_file(),(document,value))
    def test_cli_json_stays_utf8_under_legacy_windows_encoding(self):
        env=dict(os.environ,PYTHONIOENCODING='cp1252')
        result=subprocess.run([sys.executable,'-B',str(SCRIPT),'sources','--script','Cyrl','--role','body'],capture_output=True,env=env)
        self.assertEqual(result.returncode,0,result.stderr.decode('utf-8',errors='replace'))
        self.assertGreater(json.loads(result.stdout.decode('utf-8'))['count'],0)
    def test_cjk_composite_routes_and_tifinagh_are_discoverable(self):
        for script in ('Jpan','Kore','Hans','Hant','Tfng'):
            result=fc.routes(script,'body')
            self.assertGreater(result['count'],0,script)
            self.assertEqual(result['requested_script'],script)
        self.assertNotIn('Tifn',{tag for source in fc.routes()['sources'] for tag in source['scripts']})
    def test_subset_and_weight_filters_are_and_not_or(self):
        rows=fc.filter_rows(ROWS,['latin','cyrillic'],'serif',[400,700],['normal'],True)
        self.assertEqual([row['id'] for row in rows],['zeta'])
        self.assertEqual(fc.filter_rows(ROWS,['hebrew']),[])
    def test_cached_results_are_explicitly_not_fresh_and_paged(self):
        p=self.cache();code,data=self.cli('search','--input',p,'--page-size','1')
        self.assertEqual(code,0);self.assertEqual(data['mode'],'cached');self.assertEqual(data['items'][0]['id'],'alpha')
        self.assertEqual(data['next_page'],2);self.assertEqual(data['total'],3)
        _,nextpage=self.cli('search','--input',p,'--page-size','1','--page','2')
        self.assertEqual(nextpage['items'][0]['id'],'beta')
    def test_http_denial_is_unavailable_not_an_empty_catalog(self):
        with patch.object(fc,'get_metadata',return_value={'status':'unavailable','http_status':403,'url':'https://api.fontsource.org/v1/fonts'}):
            code,data=self.cli('search','--subset','cyrillic')
        self.assertEqual(code,1);self.assertEqual(data['http_status'],403);self.assertNotIn('total',data)
    def test_cache_does_not_overwrite_or_make_network_request_first(self):
        p=self.cache();before=p.read_bytes()
        with patch.object(fc,'get_metadata') as network:
            code,data=self.cli('search','--cache',p)
        self.assertEqual(code,2);network.assert_not_called();self.assertEqual(before,p.read_bytes())
    def test_bad_pages_and_bad_metadata_are_explicit(self):
        p=self.cache();self.assertEqual(self.cli('search','--input',p,'--page','0')[0],2)
        self.assertEqual(self.cli('search','--input',p,'--page','99')[0],2)
        p.write_text('{"shell":true}',encoding='utf-8');self.assertEqual(self.cli('search','--input',p)[0],2)
    def test_optional_dependency_absence_does_not_install_or_pass(self):
        p=self.root/'font.ttf';p.write_bytes(b'not-a-font')
        with patch.dict(sys.modules,{'fontTools':None,'fontTools.ttLib':None}):
            result=fc.inspect_font(p,'A')
        self.assertEqual(result['status'],'dependency_unavailable')
    def test_invalid_font_is_not_a_success(self):
        p=self.root/'font.ttf';p.write_bytes(b'not-a-font')
        status=fc.inspect_font(p,'A')['status']
        self.assertIn(status,['inspection_failed','dependency_unavailable'])
    @unittest.skipUnless(HAS_FONTTOOLS,'Optional fontTools unavailable')
    def test_binary_cmap_checks_actual_characters_not_language_labels(self):
        p=self.font();before=p.read_bytes()
        good=fc.inspect_font(p,'AА');bad=fc.inspect_font(p,'AӘё')
        self.assertEqual(good['status'],'cmap_only');self.assertEqual(bad['status'],'missing_characters')
        self.assertEqual({row['character'] for row in bad['missing']},{'Ә','ё'});self.assertEqual(before,p.read_bytes())
    @unittest.skipUnless(HAS_FONTTOOLS,'Optional fontTools unavailable')
    def test_controls_and_variation_selectors_are_sequence_tests(self):
        result=fc.inspect_font(self.font(),'A\u200d\u200c\ufe0f\U000e0100\u180b\u180d\u180f\u034f')
        self.assertEqual(result['missing'],[]);self.assertEqual(len(result['format_controls_not_cmap_tested']),8)
        result=fc.inspect_font(self.font(),'A\u0301')
        self.assertEqual(result['missing'][0]['codepoint'],'U+0301')
    def font(self):
        p=self.root/'fixture.ttf';fb=FontBuilder(1000,isTTF=True);order=['.notdef','u0041','u0410'];fb.setupGlyphOrder(order)
        fb.setupCharacterMap({0x41:'u0041',0x410:'u0410'});glyphs={}
        for name in order:
            pen=TTGlyphPen(None);pen.moveTo((50,0));pen.lineTo((300,700));pen.lineTo((550,0));pen.closePath();glyphs[name]=pen.glyph()
        fb.setupGlyf(glyphs);fb.setupHorizontalMetrics({name:(600,0) for name in order});fb.setupHorizontalHeader(ascent=800,descent=-200)
        fb.setupNameTable({'familyName':'FixtureCoverage','styleName':'Regular','uniqueFontIdentifier':'FixtureCoverage-1','fullName':'Fixture Coverage','psName':'FixtureCoverage','version':'Version 1.0'})
        fb.setupOS2(sTypoAscender=800,sTypoDescender=-200,usWinAscent=800,usWinDescent=200);fb.setupPost();fb.setupMaxp();fb.save(p);return p

if __name__=='__main__':unittest.main()
