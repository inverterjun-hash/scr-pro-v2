# -*- coding: utf-8 -*-
from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Tuple

@dataclass
class System:
    V_LL: float
    S_n: float
    f: float

    @property
    def omega(self) -> float:
        return 2*math.pi*self.f

    @property
    def Z_base(self) -> float:
        return (self.V_LL**2)/self.S_n

    @property
    def L_base(self) -> float:
        return self.Z_base/self.omega

    @property
    def V_ph(self) -> float:
        return self.V_LL/math.sqrt(3.0)

@dataclass
class RL:
    R: float = 0.0
    L: float = 0.0
    def Zabs(self, w: float) -> float:
        return math.hypot(self.R, w*self.L)

def s_sc_from_z(V_LL: float, Z_mag: float) -> float:
    return (V_LL**2)/Z_mag

def solve_line_rl_for_target_scr(sys: System, target_scr: float, r_over_l: float, tr: RL) -> RL:
    Z_target = sys.V_LL**2/(target_scr*sys.S_n)
    w=sys.omega; rho=r_over_l
    A = rho**2 + w**2
    B = 2.0*(tr.R*rho + (w**2)*tr.L)
    C = tr.R**2 + (w**2)*(tr.L**2) - (Z_target**2)
    disc = B**2 - 4*A*C
    if disc < 0: raise ValueError("목표 SCR을 만들 수 없음(해 없음).")
    L1 = (-B + math.sqrt(disc))/(2*A); L2=(-B - math.sqrt(disc))/(2*A)
    cand=[L for L in (L1,L2) if L>=0]
    if not cand: raise ValueError("양의 L 해가 없음.")
    L_line=min(cand); R_line=rho*L_line
    return RL(R_line, L_line)

def p_of_delta(V_LL: float, R: float, X: float, delta: float) -> float:
    Zabs=math.hypot(R,X); theta=math.atan2(X,R) if (R or X) else 0.0
    return (V_LL**2/Zabs)*(math.cos(theta-delta)-math.cos(theta))

def delta_from_p(V_LL: float, R: float, X: float, P: float) -> float:
    Zabs=math.hypot(R,X); theta=math.atan2(X,R) if (R or X) else 0.0
    rhs = math.cos(theta) + (P*Zabs)/(V_LL**2)
    if rhs<-1 or rhs>1: raise ValueError("요청 P가 한계를 초과.")
    return theta - math.acos(rhs)

def current_drop_limit(Vph: float, Zabs: float, target_I: float) -> float | None:
    """
    |E∠δ - V|/|Z| = I → δ를 근사 탐색 (E=V=Vph).
    """
    import numpy as np, math
    if target_I is None or target_I<=0: return None
    for d in np.linspace(0, math.radians(89.9), 2000):
        drop = 2*Vph*math.sin(d/2.0)
        I = drop/Zabs
        if I>=target_I: return d
    return None

def voltage_drop_limit(Vph: float, target_pct: float) -> float | None:
    """
    |E - V| = 2 Vph sin(δ/2). ΔV/V[%] 한계 → δ 근사.
    """
    import math
    if target_pct is None or target_pct<=0: return None
    lim = target_pct/100.0*Vph
    # 2 V sin(δ/2) >= lim
    s = lim/(2*Vph)
    if s<=0: return 0.0
    if s>=1: return math.radians(180-1e-3)
    return 2*math.asin(s)

def waveforms(sys: System, Irms: float, delta: float, Iang: float, cycles=2, ppc=400):
    import numpy as np
    T=1.0/sys.f
    t=np.linspace(0, cycles*T, cycles*ppc)
    Vph=sys.V_ph
    v_pcc=np.sqrt(2)*Vph*np.sin(sys.omega*t)
    v_inv=np.sqrt(2)*Vph*np.sin(sys.omega*t+delta)
    i_t=np.sqrt(2)*Irms*np.sin(sys.omega*t+Iang)
    return t, v_pcc, v_inv, i_t
