# SCR 계산기 Pro v2 (Android)

**무엇이 달라졌나요?**
- 프리미엄 UI(카드/아이콘/테마 토글), 단위 자동 인식(µH/mH/Ω/kV/kVA/pu), 복사 버튼
- I_max/ΔV% 한계선 오버레이가 포함된 **P–δ 그래프**
- **δ-스윕** 계산 & CSV 내보내기
- **프리셋** 저장/로드(380/400/480V 기본 제공)
- **CSV/HTML** 내보내기(그래프 이미지 포함)

## 폴더
```
app/
  main.py          # 앱 엔트리
  ui.kv            # UI 레이아웃
  scr/
    core.py        # 계산 로직
    utils.py       # 단위 파서/포맷터
  docs/guide.html  # 내장 가이드
buildozer.spec     # 안드로이드 빌드 설정
```

## (A) CMD/WSL 없이 — GitHub Actions로 APK 자동 생성
1. 이 폴더를 그대로 새 GitHub 리포지토리에 올립니다.
2. Actions 탭에서 `Android APK (Kivy/Buildozer)` 워크플로 실행(자동).
3. 완료 후 **Artifacts**에서 APK 다운로드 → 폰에 설치.

## (B) CMD/WSL에서 수동 빌드
```bash
# WSL Ubuntu에서
sudo apt update
sudo apt install -y openjdk-17-jdk python3-pip git zip unzip build-essential \
  libffi-dev libssl-dev libjpeg-dev libfreetype6-dev zlib1g-dev
python3 -m pip install --upgrade pip
python3 -m pip install buildozer Cython "kivy[base]" kivymd kivy_garden.matplotlib matplotlib numpy

# 프로젝트 폴더에서
buildozer -v android debug

# 결과: ./bin/*.apk
# 휴대폰 설치(USB 디버깅 ON)
adb install -r bin/*.apk
```

## 사용 팁
- pu 입력: R,L에 `0.1pu` 등으로 입력하면 Z_base, L_base 기준으로 자동 환산
- 단위: `50mΩ`, `75uH`, `0.38kV`, `250kVA` 등 자유롭게
- Download 폴더에 CSV/HTML 저장
