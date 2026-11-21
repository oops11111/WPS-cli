"""Original measured snapshots plus fresh source-audit metadata; never exports WPS."""
import argparse
import copy
import hashlib
import json
import zipfile
from pathlib import Path
from unittest.mock import patch
from wps_ai_agent_cli import html_styles
from wps_ai_agent_cli.html_editable import _walk,convert_html_editable
from wps_ai_agent_cli.docx_styling import qualified_horizontal_print_margins
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True);args=parser.parse_args()
ROOT=Path.cwd();BASE=ROOT/'artifacts/alignment-aware-print-margins-20261121';OUT=args.out;OUT.mkdir(parents=True,exist_ok=False)
results={}
for folder in sorted(BASE.glob('A-*-docx')):
    source=next((folder/'input').glob('*.html'));old=json.loads((folder/'browser-styles.json').read_text());expected=json.loads((ROOT/'artifacts/alignment-aware-margins-preflight-20261121'/(folder.name+'-qualification.json')).read_text())['eligible']
    styled=html_styles.load(source,use_browser=True);fresh=copy.deepcopy(styled.print_context)
    without_added=copy.deepcopy(fresh);del without_added['cssom']['style_sources']
    assert without_added==old['print_context'],(folder.name,'old metadata changed')
    sources=fresh['cssom']['style_sources'];assert sources=={'checked':True,'document_adopted_count':0,'open_shadow_root_count':0}
    before_hash=hashlib.sha256((folder/'converted.docx').read_bytes()).hexdigest()
    assert before_hash==json.loads((folder/'result.json').read_text())['hashes']['converted.docx']
    byid={e['attrs'].get('data-wps-i'):e for e in old['elements']}
    for n in _walk(styled.root):
        e=byid.get(n.attrs.get('data-wps-i'))
        if e:
            styled.styles[id(n)]=e['style']
            if e['box'] is not None:styled.boxes[id(n)]=e['box']
            if e.get('summary_marker'):styled.summary_markers[id(n)]=e['summary_marker']
    styled.mode=old['mode'];styled.browser=old['browser'];styled.warnings=old['warnings']
    eligible=qualified_horizontal_print_margins(styled,'editable');assert eligible==expected
    reference=folder/'converted.docx';target=OUT/(folder.name+'-replay.docx')
    with zipfile.ZipFile(reference) as z:infos={i.filename:copy.copy(i) for i in z.infolist()}
    original_write=zipfile.ZipFile.writestr
    def write_fixed(self,zinfo,data,*args,infos=infos,original_write=original_write,**kwargs):
        name=zinfo.filename if isinstance(zinfo,zipfile.ZipInfo) else zinfo
        return original_write(self,copy.copy(infos[name]),data,*args,**kwargs)
    with patch.object(html_styles,'load',return_value=styled),patch.object(zipfile.ZipFile,'writestr',write_fixed):result=convert_html_editable(source,target,use_browser=False)
    assert result[0],result
    with zipfile.ZipFile(reference) as a,zipfile.ZipFile(target) as b:
        assert a.namelist()==b.namelist() and all(a.read(n)==b.read(n) for n in a.namelist())
    assert reference.read_bytes()==target.read_bytes()
    assert hashlib.sha256(reference.read_bytes()).hexdigest()==before_hash
    results[folder.name]={'original_wps_manifest_hash_verified':True,'old_wps_input_sha256':before_hash,'new_replay_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'all_package_payloads_identical':True,'full_docx_bytes_identical':True,'old_eligibility':expected,'new_eligibility':eligible,'original_metadata_identical_except_added_source_audit':True,'new_print_context':fresh}
    (OUT/'verification.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
    print(folder.name,'full bytes and eligibility identical',flush=True)
