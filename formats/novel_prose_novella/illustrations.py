"""Novel-only chapter illustration decisions; source text is never modified."""
import re,math
from copy import deepcopy


def recommendations(snapshot):
    from core.manuscript_structure import unit_plan,blocks
    writing=blocks(snapshot);chapters={}
    for row in unit_plan(snapshot):
        chapter=chapters.setdefault(row['group_number'],[])
        chapter.append(row['group_title']+' '+writing.get(row['unit_id'],''))
    candidates=[]
    for n,parts in chapters.items():
        text=' '.join(parts)
        matches=re.findall(r'\b(map|landscape|panorama|portrait|photograph|sketch|diagram|reveal|discovery|landmark)\b',text,re.I)
        if not matches:continue
        lower=' '.join(matches).lower()
        if re.search(r'map|diagram',lower):placement,width,height,align='chapter_end',6,3,'center'
        elif re.search(r'portrait|photograph',lower):placement,width,height,align='chapter_end',2.5,3,'right'
        else:placement,width,height,align='chapter_start',5.5,2.4,'center'
        candidates.append((len(matches),n,dict(placement=placement,width=width,height=height,alignment=align,reason='Visual story detail in this saved chapter: '+', '.join(sorted(set(m.lower() for m in matches))))))
    # Sparse recommendations only; no generic illustration per chapter.
    limit=max(1,math.ceil(len(chapters)/4))
    return {'chapter-'+str(n):info for _,n,info in sorted(candidates,key=lambda x:(-x[0],x[1]))[:limit]}


def chapter_slot(snapshot,anchor,base,raw):
    result=deepcopy(base);original=(raw.get('positions') or {}).get(anchor) or {}
    style=raw.get('layout_style','');recommendation=recommendations(snapshot).get(anchor) if style=='adaptive' else None
    if recommendation:
        for key in ('placement','width','height','alignment'):
            if key not in original:result[key]=recommendation[key]
    result['enabled']=original.get('enabled',bool(recommendation))
    result['placement']=original.get('placement',result.get('placement','chapter_start'))
    result['recommendation']=recommendation['reason'] if recommendation else 'No automatic illustration recommended for this chapter.'
    return result
