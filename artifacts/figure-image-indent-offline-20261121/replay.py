"""Offline Stage22 hard gate; never starts a renderer."""
import copy
import hashlib
import json
import zipfile
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree as ET

from wps_ai_agent_cli import html_styles
from wps_ai_agent_cli.html_editable import _walk, convert_html_editable

ROOT=Path.cwd()
BASE=ROOT/'artifacts/closed-summary-marker-20261121'
OUT=ROOT/'artifacts/figure-image-indent-offline-20261121'
OUT.mkdir(exist_ok=True)
W='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
results={}
for folder in sorted(BASE.glob('A-*-docx')):
    records=json.loads((folder/'browser-styles.json').read_text())
    source=next((folder/'input').glob('*.html'))
    styled=html_styles.load(source,use_browser=False)
    byid={e['attrs'].get('data-wps-i'): e for e in records['elements']}
    for node in _walk(styled.root):
        record=byid.get(node.attrs.get('data-wps-i'))
        if record:
            styled.styles[id(node)]=record['style']
            if record['box'] is not None: styled.boxes[id(node)]=record['box']
            if record.get('summary_marker'): styled.summary_markers[id(node)]=record['summary_marker']
    styled.mode='browser';styled.browser=records['browser'];styled.warnings=records['warnings']
    reference=folder/'converted.docx'
    with zipfile.ZipFile(reference) as z: infos={i.filename:copy.copy(i) for i in z.infolist()}
    original_write=zipfile.ZipFile.writestr
    def write_fixed(self,zinfo,data,*args,**kwargs):
        name=zinfo.filename if isinstance(zinfo,zipfile.ZipInfo) else zinfo
        return original_write(self,copy.copy(infos[name]),data,*args,**kwargs)
    target=OUT/(folder.name+'.docx')
    with patch.object(html_styles,'load',return_value=styled),patch.object(zipfile.ZipFile,'writestr',write_fixed):
        converted=convert_html_editable(source,target,use_browser=False)
    assert converted[0],converted
    changed=[];bad=[]
    with zipfile.ZipFile(reference) as old,zipfile.ZipFile(target) as new:
        assert old.namelist()==new.namelist()
        for name in old.namelist():
            a,b=old.read(name),new.read(name)
            if a==b: continue
            changed.append(name)
            if name!='word/document.xml': bad.append(name);continue
            ra,rb=ET.fromstring(a),ET.fromstring(b)
            added=[]
            for index,p in enumerate(rb.findall('.//'+W+'body/'+W+'p')):
                ind=p.find(W+'pPr/'+W+'ind')
                if ind is not None and ind.get(W+'left')=='600' and p.find('.//'+W+'drawing') is not None:
                    p.find(W+'pPr').remove(ind);added.append(index)
            if len(added)!=1 or ET.tostring(ra)!=ET.tostring(rb): bad.append(name+':not-single-image-left600')
    results[folder.name]={'changed_parts':changed,'unexpected':bad,'full_bytes_identical':reference.read_bytes()==target.read_bytes(),'candidate_sha256':hashlib.sha256(target.read_bytes()).hexdigest()}
    print(folder.name,results[folder.name],flush=True)
    (OUT/'package-gate.json').write_text(json.dumps(results,indent=2)+'\n')
    if bad or ('report' not in folder.name and reference.read_bytes()!=target.read_bytes()):
        raise SystemExit('STOP: package gate failed')
