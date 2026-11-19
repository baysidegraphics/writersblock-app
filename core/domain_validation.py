"""Pure table/reference validation, without external fact verification."""
import re
from datetime import date


def records(values,name,errors):
    rows=values.get(name,[])
    if not isinstance(rows,list) or any(not isinstance(row,dict) for row in rows):
        errors.append(f'{name}: expected table records.');return []
    return rows


def identifiers(rows,key,errors):
    values=[str(row.get(key) or '').strip() for row in rows]
    if any(not value for value in values):errors.append(f'{key}: every row needs an identifier.')
    if len(values)!=len(set(values)):errors.append(f'{key}: duplicate identifiers are not allowed.')
    return set(values)-{''}


def refs(value):
    if isinstance(value,list):return [str(v).strip() for v in value if str(v).strip()]
    return [v.strip() for v in str(value or '').split(',') if v.strip()]


def check_refs(value,known,label,errors):
    if set(refs(value))-known:errors.append(f'{label}: references an unknown identifier.')


def number(value):
    try:
        parsed=int(str(value))
        return parsed if parsed>0 else None
    except (ValueError,TypeError):return None


def check_date(value,label,errors):
    text=str(value or '').strip()
    if not text or text.lower() in {'unknown','approximate'}:return
    if re.fullmatch(r'\d{4}',text):return
    try:date.fromisoformat(text)
    except (ValueError,TypeError):errors.append(f'{label}: use YYYY, YYYY-MM-DD, unknown or approximate; explain uncertainty in notes.')


def require_text(value,label,errors):
    if not isinstance(value,str) or not value.strip():errors.append(f'{label} is required.')
