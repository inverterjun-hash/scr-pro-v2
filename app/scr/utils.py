# -*- coding: utf-8 -*-
import re, math

SI = {
    'n': 1e-9, 'u': 1e-6, 'µ': 1e-6, 'm': 1e-3,
    '': 1.0, 'k': 1e3, 'K': 1e3, 'M': 1e6, 'G': 1e9
}

def _si_prefix(text: str):
    m = re.search(r'([numkKMµG]?)(?![a-zA-Z])', text)
    if not m: return 1.0
    pre = m.group(1) or ''
    return SI.get(pre, 1.0)

def parse_value(s: str, kind: str, *, pu=False, Z_base=1.0, L_base=1.0, default=0.0):
    """
    kind: 'R','L','V','S','F','I','P','pct'
    입력 예: '75uH', '0.2 mH', '50mΩ', '0.1pu', '380 V', '0.75 MVA', '2.5 kW'
    """
    if s is None: return default
    text = str(s).strip()
    if not text: return default
    # pu 우선 처리
    if 'pu' in text.lower():
        try:
            val = float(re.findall(r'[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?', text)[0])
        except:
            return default
        if not pu:  # pu 입력 허용일 때만 적용
            return default
        if kind=='R': return val*Z_base
        if kind=='L': return val*L_base
        if kind=='V': return val*(Z_base**0.5)  # 잘 쓰지 않음
        if kind=='I': return val*(1/Z_base**0.5)
        return default

    # 숫자 추출
    nums = re.findall(r'[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?', text.replace(',', ''))
    if not nums: return default
    v = float(nums[0])

    # 단위 처리
    t = text.lower()
    if kind=='R':
        # Ω, mΩ, kΩ
        if 'mω' in t or 'mohm' in t: return v*1e-3
        if 'kω' in t or 'kohm' in t: return v*1e3
        if 'ω' in t or 'ohm' in t: return v
        # 접미사 없는 경우
        return v
    if kind=='L':
        # H, mH, uH
        if 'uh' in t or 'µh' in t: return v*1e-6
        if 'mh' in t: return v*1e-3
        if 'h' in t: return v
        return v  # 기본 H
    if kind=='V':
        if 'kv' in t: return v*1e3
        return v
    if kind=='S':
        if 'mva' in t: return v*1e6
        if 'kva' in t: return v*1e3
        return v
    if kind=='F':
        return v
    if kind=='I':
        if 'ka' in t: return v*1e3
        return v
    if kind=='P':
        if 'mw' in t: return v*1e6
        if 'kw' in t: return v*1e3
        return v
    if kind=='pct':
        return v
    return v

def fmt_num(x, unit='', digits=6, sci=False):
    try:
        if sci:
            s = f"{x:.3e}"
        else:
            s = f"{x:.{digits}f}"
    except Exception:
        s = str(x)
    return f"{s} {unit}".strip()
