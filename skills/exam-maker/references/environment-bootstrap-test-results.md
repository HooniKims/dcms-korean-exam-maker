# 한글 우선·조건부 에디터 준비 검증 — v1.10.8

검증일 2026-10-07. 아래 v1.7.0의 무조건 에디터 준비는 당시 동작 기록이며, 현재 기본값은 이 항목을 따른다.

- Windows 실제 `bootstrap_windows.ps1 -Apply` 실행: 한글2024 발견, `workflow=hancom`, `status=READY`, `editor_required=false`, `editor_smoke.status=SKIPPED_NATIVE`, `actions=[]`. 에디터·Git·Node·Python 설치 단계에 진입하지 않았다.
- PowerShell 시작 스크립트에 Python 탐색 시 실패하는 대역을 넣어도 한글 발견 시 정상 종료했다. Python 자체가 없어도 네이티브 편집 경로를 막지 않는다.
- Python 진입점에서 한글 발견 시 도구/스킬/문서 패키지 설치와 subprocess 실행이 모두 금지된 대역으로 정상 종료를 검증했다. 명시적 editor 옵션에서는 대체 경로에 진입한다.
- macOS 앱 번들 모형: 실제 실행 파일이 있는 한글/Hanword만 인정하고 뷰어·한셀·실행 파일 없는 앱은 제외한다. 한글이 있으면 에디터 준비 생략, 없으면 읽기 전용 MISSING 및 apply 설치/엔진 확인 경로를 검증했다. **Mac 실기 설치·화면 검수는 수행하지 않았다.**
- 레지스트리를 읽을 수 없는 Windows 환경에서도 해당 항목을 건너뛰고 설치 폴더 검색으로 계속한다. 시스템 보안 설정을 바꾸지 않는다.
- 전체 회귀158개 PASS(17.395초). 이 기록은 환경 선택/설치 경로 검증이며 시험지 조판 합격을 뜻하지 않는다.

---

# 자동 환경 준비 검증 기록

검증일2026-10-05, Windows. v1.7.0 부트스트랩의 실제 설치·재실행을 확인했다.

| 검사 | 결과 |
|---|---|
| 현재 PC의 PowerShell 시작 스크립트→Python 부트스트랩 | READY |
| 기존 Git2.53.0·Node24.13.0·npm11.6.2 재사용 | 추가 설치0건 |
| 기존 HWPX 스킬의 파일·사용자 수정 보존 | pull/덮어쓰기 없음 |
| 한글2024 실제 탐색 | COM 등록+설치 폴더에서 HOffice130/Bin/Hwp.exe 발견 |
| 빈 격리 폴더에 HWPX 스킬 실제 다운로드 | 지정한 GitHub 커밋 설치 성공 |
| 새 설치본 에디터 소스 준비·npm 의존성 설치·빌드 | 성공 |
| 새 설치본 WASM 초기화·실제 빈 HWPX 파싱 | PASS |
| 새 설치본에 같은 --apply 재실행 | READY, 추가 설치/빌드0건 |
| 없는 스킬 폴더 읽기 전용 점검 | MISSING, 폴더 생성/설치 없음 |
| 버전·이름·공백 경로·뷰어 제외·기존 스킬 보존·설치 실패 처리 테스트 | 17개 PASS |
| PowerShell 구문 검사 | PASS |

설치 과정에서 upstream의 기본 전체 clone이 약1.9GB의 자료를 받는 것을 발견했다. Rust 도구가 없는 일반 설치는 partial clone과 sparse checkout으로 에디터/SDK만 받도록 수정하여 Git pack을 약11MB로 줄였다. PDF 대용량 시험 자료의 Git LFS 자동 다운로드도 생략했다. 이 경로로 빈 폴더에서 전체 빌드와 엔진 파싱을 다시 통과했다. 기존 스킬의 setup.mjs는 수정하지 않았다.

한글2020·‘한컴오피스2020’·‘한글2024’·사용자 지정 설치 경로는 파일/등록 정보 모형으로 탐색을 검증했다. 실제 설치 제품은 한글2024이며,2020 실기 편집이나 Mac 실기 검증을 했다는 뜻은 아니다. Git/Node/Python은 현재 PC에 이미 있어 제거 후 재설치하지 않았다. 누락 시 정확한 WinGet ID로 설치하고 실행 결과를 재검사하는 분기는 테스트 대역으로 검증했고, HWPX 스킬과 에디터 빌드는 격리 폴더에서 실제로 수행했다.

테스트 산출물: 작업 폴더의 tmp/exam-bootstrap/environment.json, clean-install.json, second-run.json, missing-dry-run.json, tests.txt. 에디터 빌드 로그는 CODEX_HOME/cache/exam-maker/editor-setup.log. 전역 HWPX 스킬은 이미 존재하므로 재설치하지 않았다. 시험지는 한글 직접 편집 경로로 유지했다.
