# -*- coding: utf-8 -*-
import os, io, base64, math, datetime, json
from pathlib import Path

from kivy.utils import platform
from kivy.lang import Builder
from kivy.core.clipboard import Clipboard
from kivy.core.window import Window
from kivy.uix.boxlayout import BoxLayout

from kivymd.app import MDApp
from kivymd.uix.tab import MDTabsBase
from kivymd.uix.snackbar import Snackbar

from scr.core import System, RL, s_sc_from_z, solve_line_rl_for_target_scr, p_of_delta, delta_from_p, waveforms, current_drop_limit, voltage_drop_limit
from scr.utils import parse_value, fmt_num

# Plot stack
_use_plots = True
try:
    import numpy as np
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib.figure import Figure
    from kivy_garden.matplotlib.backend_kivyagg import FigureCanvasKivyAgg
    matplotlib.rcParams['font.family'] = ["Malgun Gothic","AppleGothic","NanumGothic","Noto Sans CJK KR","DejaVu Sans"]
    matplotlib.rcParams['axes.unicode_minus'] = False
except Exception:
    _use_plots = False

class ContentTab(BoxLayout, MDTabsBase):
    pass

class State:
    def __init__(self, app):
        self.app=app
        self.last_result=None
        self.last_line=None
        self.last_plot_pngs={}
        self.logs=[]; self.sweep_rows=[]; self.presets={}

    def log(self, msg):
        ts=datetime.datetime.now().strftime("%H:%M:%S")
        self.logs.append(f"[{ts}] {msg}")
        self.app.log_text="\\n".join(self.logs)[-9000:]

class SCRProV2(MDApp):
    # defaults
    V_LL="380"; S_n="250000"; f_hz="60"
    R_line="0.0"; L_line="7.5e-05"
    R_tr="0.0"; L_tr="0.0"
    target_scr="3.0"; r_over_l="0.0"
    P_kW="1000"; delta_deg="10"; I_max=""; V_drop_pct=""
    sweep_deg_max="60"; sweep_step="0.5"

    scr_summary="여기에 SCR 계산 결과가 표시됩니다."
    line_summary="여기에 선로 RL 산출 결과가 표시됩니다."
    vis_summary="여기에 시각화 결과가 표시됩니다."
    sweep_summary="스윕 결과가 여기에 표시됩니다."
    presets_summary="프리셋 목록이 여기에 표시됩니다."
    log_text=""
    pu_mode=False

    def build(self):
        self.title="SCR 계산기 Pro v2"
        self.theme_cls.theme_style="Light"
        self.state=State(self)
        (Path(self.user_data_dir)/"exports").mkdir(parents=True, exist_ok=True)
        # load presets
        self._load_presets()
        kv_path=Path(__file__).with_name("ui.kv")
        return Builder.load_string(kv_path.read_text(encoding="utf-8"))

    # --- Theme ---
    def toggle_theme(self):
        self.theme_cls.theme_style="Dark" if self.theme_cls.theme_style=="Light" else "Light"

    # --- PU ---
    def set_pu(self, active): self.pu_mode=bool(active)

    # --- utility ---
    def _sys_from(self, VLL, Sn, f):
        # 단위/pu 지원
        sys_tmp=System( parse_value(VLL,'V'), parse_value(Sn,'S'), parse_value(f,'F') )
        return sys_tmp

    def _downloads(self): return "/sdcard/Download" if platform=="android" else str(Path.cwd())

    def open_guide(self):
        Snackbar(text="가이드는 /app/docs/guide.html 을 브라우저로 여세요.").open()

    # --- calc SCR ---
    def calc_scr(self, VLL, Sn, f, R_line, L_line, R_tr, L_tr):
        try:
            sys=self._sys_from(VLL,Sn,f)
            Rl=parse_value(R_line,'R', pu=self.pu_mode, Z_base=sys.Z_base, L_base=sys.L_base)
            Ll=parse_value(L_line,'L', pu=self.pu_mode, Z_base=sys.Z_base, L_base=sys.L_base)
            Rtr=parse_value(R_tr,'R', pu=self.pu_mode, Z_base=sys.Z_base, L_base=sys.L_base)
            Ltr=parse_value(L_tr,'L', pu=self.pu_mode, Z_base=sys.Z_base, L_base=sys.L_base)
            line=RL(Rl,Ll); tr=RL(Rtr,Ltr)
            Zabs=RL(line.R+tr.R, line.L+tr.L).Zabs(sys.omega)
            Ssc=s_sc_from_z(sys.V_LL, Zabs); SCR=Ssc/sys.S_n
            Ir=sys.S_n/(math.sqrt(3)*sys.V_LL); Isc=Ssc/(math.sqrt(3)*sys.V_LL); ratio=Isc/Ir if Ir>0 else float("nan")
            self.scr_summary=(
                f"[SCR 계산]\\n|Z_th| = {Zabs:.6f} Ω/상\\nS_sc = {Ssc/1e6:.3f} MVA, SCR={SCR:.3f}\\nI_sc/I_r = {ratio:.3f}\\n"
            )
            self.state.last_result=dict(V_LL=sys.V_LL,S_n=sys.S_n,f=sys.f, R_line=line.R,L_line=line.L,R_tr=tr.R,L_tr=tr.L, Zth=Zabs,S_sc=Ssc,SCR=SCR,I_ratio=ratio)
            self.state.log("SCR 계산 완료")
        except Exception as e:
            self.scr_summary=f"오류: {e}"; self.state.log(f"SCR 오류: {e}")

    # --- calc line ---
    def calc_line(self, VLL, Sn, f, target_scr, r_over_l, R_tr, L_tr):
        try:
            sys=self._sys_from(VLL,Sn,f)
            Rtr=parse_value(R_tr,'R', pu=self.pu_mode, Z_base=sys.Z_base, L_base=sys.L_base)
            Ltr=parse_value(L_tr,'L', pu=self.pu_mode, Z_base=sys.Z_base, L_base=sys.L_base)
            rho=parse_value(r_over_l,'R')/max(parse_value("1",'L'),1e-12) if 'pu' not in str(r_over_l).lower() else float(r_over_l) # 간단화
            target=float(target_scr)
            line=solve_line_rl_for_target_scr(sys, target, rho, RL(Rtr,Ltr))
            Zabs=RL(line.R+Rtr, line.L+Ltr).Zabs(sys.omega); Ssc=s_sc_from_z(sys.V_LL, Zabs); SCR=Ssc/sys.S_n
            self.line_summary=(
                f"[선로 RL 산출]\\nR_line={line.R:.6f} Ω/상, L_line={line.L:.9e} H/상\\n|Z_th|={Zabs:.6f} Ω/상, S_sc={Ssc/1e6:.3f} MVA, SCR={SCR:.3f}\\n"
            )
            self.state.last_line=dict(R_line=line.R,L_line=line.L,Zth=Zabs,S_sc=Ssc,SCR=SCR)
            self.state.log("선로 RL 산출 완료")
        except Exception as e:
            self.line_summary=f"오류: {e}"; self.state.log(f"RL 산출 오류: {e}")

    # --- visualize ---
    def visualize(self, P_kW, delta_deg, Imax, Vdpct):
        if not _use_plots:
            self.vis_summary="그래프 모듈 불가 (matplotlib/garden 미설치)"; return
        src=self.state.last_result or {}
        sys=System(float(src.get('V_LL', parse_value(self.V_LL,'V'))),
                   float(src.get('S_n', parse_value(self.S_n,'S'))),
                   float(src.get('f', parse_value(self.f_hz,'F'))))
        R=float(src.get('R_line', parse_value(self.R_line,'R'))) + float(src.get('R_tr', parse_value(self.R_tr,'R')))
        X=sys.omega*(float(src.get('L_line', parse_value(self.L_line,'L'))) + float(src.get('L_tr', parse_value(self.L_tr,'L'))))
        VLL=sys.V_LL; Vph=sys.V_ph; Zabs=math.hypot(R,X); theta=math.atan2(X,R) if (R or X) else 0.0

        P_in=parse_value(P_kW,'P'); d_in=math.radians(float(delta_deg or 0))
        try:
            if P_in>0:
                delta=delta_from_p(VLL,R,X,P_in); P=P_in
            else:
                delta=d_in; P=p_of_delta(VLL,R,X,delta)
        except Exception as e:
            self.vis_summary=f"시각화 오류: {e}"; return

        E=Vph*complex(math.cos(delta), math.sin(delta))
        V=complex(Vph,0.0); Z=complex(R,X)
        I=(E-V)/Z if Zabs>0 else complex(0,0)
        Irms=abs(I); Iang=math.atan2(I.imag,I.real)
        Pmax=(VLL**2/Zabs)*(1-math.cos(theta)) if Zabs>0 else 0.0

        # 캔버스 정리
        area=self.root.ids.plot_area; area.clear_widgets()
        import numpy as np
        fig=Figure(figsize=(6,3), dpi=120); ax1=fig.add_subplot(121); ax2=fig.add_subplot(122)

        # Phasor
        vmax=Vph*1.25
        ax1.arrow(0,0,Vph,0, head_width=0.03*Vph, length_includes_head=True, color="#93c5fd", label="V")
        ax1.arrow(0,0,Vph*math.cos(delta),Vph*math.sin(delta), head_width=0.03*Vph, length_includes_head=True, color="#34d399", label="E")
        drop=(E-V)
        ax1.arrow(Vph*math.cos(delta),Vph*math.sin(delta), -drop.real, -drop.imag, head_width=0.03*Vph, length_includes_head=True, color="#f59e0b", label="ΔV")
        ax1.set_aspect('equal'); ax1.set_xlim(-vmax,vmax); ax1.set_ylim(-vmax,vmax); ax1.set_title("Phasor")
        ax1.legend(fontsize=8, loc="upper left")

        # P–δ
        del_max=min(theta, math.radians(89.9))
        ds=np.linspace(0, del_max, 400)
        Pcurve=(VLL**2/Zabs)*(np.cos(theta-ds)-np.cos(theta)) if Zabs>0 else np.zeros_like(ds)
        ax2.plot(np.degrees(ds), Pcurve/1e6, label="P(δ)")
        ax2.scatter([math.degrees(delta)], [P/1e6], s=18, color="#ef4444", label="현재")
        # 한계선
        Imax_val=parse_value(Imax,'I') if Imax else None
        Vpct_val=parse_value(Vdpct,'pct') if Vdpct else None
        dI=current_drop_limit(Vph,Zabs,Imax_val) if Imax_val else None
        dV=voltage_drop_limit(Vph,Vpct_val) if Vpct_val else None
        for dval, lab, col in [(dI,"I_max", "#f59e0b"), (dV,"ΔV%", "#a78bfa")]:
            if dval:
                ax2.axvline(math.degrees(dval), color=col, linestyle="--", label=f"{lab} @ {math.degrees(dval):.1f}°")
        ax2.set_xlabel("δ [deg]"); ax2.set_ylabel("P [MW]"); ax2.grid(True, alpha=.3); ax2.legend(fontsize=8); ax2.set_title("P–δ + 한계")

        area.add_widget(FigureCanvasKivyAgg(fig))

        # Waveforms
        fig2=Figure(figsize=(6,3), dpi=120); axw=fig2.add_subplot(111)
        t, v_pcc, v_inv, i_t = waveforms(sys, Irms, delta, Iang, cycles=2, ppc=400)
        axw.plot(t*1e3, v_pcc, label="v_pcc[V]"); axw.plot(t*1e3, v_inv, label="v_inv[V]"); axw.plot(t*1e3, i_t, label="i[A]")
        axw.set_xlabel("t [ms]"); axw.grid(True, alpha=.3); axw.legend(fontsize=8); axw.set_title("Time waveforms")
        area.add_widget(FigureCanvasKivyAgg(fig2))

        # summary & cache
        self.vis_summary=f"P={P/1e6:.3f} MW, δ={math.degrees(delta):.2f}°, P_max={Pmax/1e6:.3f} MW | I={Irms:.1f} A"
        self.state.last_plot_pngs={"phas_pdelta": self._fig_to_b64(fig), "wave": self._fig_to_b64(fig2)}

    def _fig_to_b64(self, fig):
        import io, base64
        buf=io.BytesIO(); fig.savefig(buf, format="png", dpi=140, bbox_inches="tight"); data=base64.b64encode(buf.getvalue()).decode("ascii"); buf.close(); return data

    # --- sweep ---
    def run_sweep(self, dmax, step):
        src=self.state.last_result or {}
        if not src: self.sweep_summary="먼저 계산을 수행하세요."; return
        sys=System(src["V_LL"], src["S_n"], src["f"])
        R=src.get("R_line",0)+src.get("R_tr",0); X=sys.omega*(src.get("L_line",0)+src.get("L_tr",0))
        import numpy as np, math
        dmax_rad=math.radians(float(dmax or 60)); step_deg=float(step or 0.5)
        ds=np.arange(0, math.degrees(dmax_rad)+1e-9, step_deg)
        rows=[]
        for deg in ds:
            d=math.radians(deg)
            P=p_of_delta(sys.V_LL,R,X,d)
            I=abs((sys.V_ph*(complex(math.cos(d), math.sin(d)) - 1+0j)) / complex(R,X)) if (R or X) else 0.0
            drop=2*sys.V_ph*math.sin(d/2)
            rows.append(dict(delta_deg=deg, P_MW=P/1e6, I_A=I, dV_pct=(drop/sys.V_ph*100)))
        self.state.sweep_rows=rows
        self.sweep_summary="δ,P[MW],I[A],ΔV[%]\\n" + "\\n".join([f"{r['delta_deg']:.2f},{r['P_MW']:.6f},{r['I_A']:.3f},{r['dV_pct']:.3f}" for r in rows])
        self.state.log(f"δ-스윕 {len(rows)}포인트 완료")

    def save_sweep_csv(self):
        if not self.state.sweep_rows: Snackbar(text="스윕 데이터가 없습니다").open(); return
        base=self._downloads(); ts=datetime.datetime.now().strftime("%Y%m%d_%H%M%S"); path=os.path.join(base, f"delta_sweep_{ts}.csv")
        import csv
        keys=["delta_deg","P_MW","I_A","dV_pct"]
        with open(path,"w",newline="",encoding="utf-8-sig") as f:
            w=csv.DictWriter(f, fieldnames=keys); w.writeheader(); [w.writerow(r) for r in self.state.sweep_rows]
        Snackbar(text=f"CSV 저장: {path}").open()

    # --- presets ---
    def _preset_path(self): return Path(self.user_data_dir)/"presets.json"
    def _load_presets(self):
        # 기본 프리셋
        base={"380V/60Hz": {"V_LL":"380","S_n":"250000","f_hz":"60"},
              "400V/50Hz": {"V_LL":"400","S_n":"250000","f_hz":"50"},
              "480V/60Hz": {"V_LL":"480","S_n":"250000","f_hz":"60"}}
        p=self._preset_path()
        if p.exists():
            try: self.state.presets=json.loads(p.read_text(encoding="utf-8"))
            except: self.state.presets=base
        else:
            self.state.presets=base; p.write_text(json.dumps(base,ensure_ascii=False,indent=2), encoding="utf-8")
        self._refresh_presets_summary()

    def _refresh_presets_summary(self):
        lines=[f"- {k}: V_LL={v['V_LL']}, S_n={v['S_n']}, f={v['f_hz']}" for k,v in self.state.presets.items()]
        self.presets_summary="\\n".join(lines)

    def save_preset(self, name):
        name=(name or "").strip() or datetime.datetime.now().strftime("custom-%H%M%S")
        self.state.presets[name]={"V_LL":self.V_LL,"S_n":self.S_n,"f_hz":self.f_hz}
        self._preset_path().write_text(json.dumps(self.state.presets,ensure_ascii=False,indent=2), encoding="utf-8")
        self._refresh_presets_summary()
        Snackbar(text=f"프리셋 저장: {name}").open()

    def load_default_presets(self):
        (Path(self.user_data_dir)/"presets.json").unlink(missing_ok=True)
        self._load_presets(); Snackbar(text="기본 프리셋 재생성").open()

    # --- export ---
    def export_csv(self):
        rows=[]; 
        if self.state.last_result: rows.append({"type":"scr", **self.state.last_result})
        if self.state.last_line: rows.append({"type":"line", **self.state.last_line})
        if not rows: Snackbar(text="저장할 데이터 없음").open(); return
        ts=datetime.datetime.now().strftime("%Y%m%d_%H%M%S"); base=self._downloads(); path=os.path.join(base, f"scr_results_{ts}.csv")
        import csv
        keys=sorted(set().union(*[r.keys() for r in rows]))
        with open(path,"w",newline="",encoding="utf-8-sig") as f:
            w=csv.DictWriter(f, fieldnames=keys); w.writeheader(); [w.writerow(r) for r in rows]
        Snackbar(text=f"CSV 저장: {path}").open()

    def export_html(self):
        r=self.state.last_result
        if not r: Snackbar(text="보고서용 결과가 없습니다").open(); return
        css="body{font-family:system-ui,Segoe UI,Roboto,'Apple SD Gothic Neo',Noto Sans KR,Malgun Gothic,sans-serif;background:#0f172a;color:#e2e8f0;margin:0} .wrap{max-width:980px;margin:0 auto;padding:24px} .card{background:#111827;border:1px solid #1f2937;border-radius:12px;padding:16px;margin:12px 0} table{width:100%;border-collapse:collapse} th,td{border:1px solid #1f2937;padding:8px 10px} th{background:#0b1220} img{max-width:100%}"
        rows=[("SCR", f"{r['SCR']:.3f}"),("S_sc [MVA]", f"{r['S_sc']/1e6:.3f}"),("|Z_th| [Ω/상]", f"{r['Zth']:.6f}"),("I_sc/I_r", f"{r['I_ratio']:.3f}"),
              ("V_LL [V]", f"{r['V_LL']:.1f}"),("S_n [VA]", f"{r['S_n']:.0f}"),("f [Hz]", f"{r['f']:.1f}"),
              ("R_line [Ω/상]", f"{r.get('R_line',0):.6f}"),("L_line [H/상]", f"{r.get('L_line',0):.9e}"),
              ("R_tr [Ω/상]", f"{r.get('R_tr',0):.6f}"),("L_tr [H/상]", f"{r.get('L_tr',0):.9e}")]
        table="".join([f"<tr><th>{k}</th><td>{v}</td></tr>" for k,v in rows])
        html=f"<!doctype html><meta charset='utf-8'><title>SCR Report</title><style>{css}</style><div class='wrap'><h1>SCR 계산기 Pro v2 보고서</h1><div class='card'><table>{table}</table></div><div class='card'><h3>Phasor & P–δ</h3><img src='data:image/png;base64,{self.state.last_plot_pngs.get('phas_pdelta','')}'/></div><div class='card'><h3>Time waveforms</h3><img src='data:image/png;base64,{self.state.last_plot_pngs.get('wave','')}'/></div></div>"
        base=self._downloads(); ts=datetime.datetime.now().strftime("%Y%m%d_%H%M%S"); path=os.path.join(base, f"scr_report_{ts}.html")
        with open(path,"w",encoding="utf-8") as f: f.write(html)
        Snackbar(text=f"HTML 보고서 저장: {path}").open()

    # --- copy ---
    def copy_log(self): Clipboard.copy(self.log_text or ""); Snackbar(text="로그 복사").open()
    def clear_log(self): self.state.logs.clear(); self.log_text=""; Snackbar(text="로그 초기화").open()
    def copy_result(self, which):
        txt = self.scr_summary if which=='scr' else self.line_summary
        Clipboard.copy(txt or ""); Snackbar(text="결과 복사").open()

if __name__ == "__main__":
    SCRProV2().run()
