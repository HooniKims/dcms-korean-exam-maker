# 실행 환경 자동 준비와 한글 검색

사용자 지정(2026-10-05): 이 스킬을 실행하면 HWPX 에디터 스킬과 필요한 Git·Node.js 등의 설치 여부를 검사하고, 없다면 안내 후 자동 설치한다. 이 사용자에게 같은 설치 허가를 다시 묻지 않는다. 시스템의 실제 권한 제한이나 보안 대화상자는 우회하지 않는다.

## 매 실행의 첫 단계

1. OS와 스킬 경로를 확인한다. 사용자에게 “HWPX 에디터와 필요한 Git·Node.js·Python을 확인하고, 없는 구성요소만 자동 설치하겠습니다. 기존 설치는 재사용합니다.”라고 알린다. 설치 소요 시간이 길어지면 진행 상황을 알린다.
2. `load_workspace_dependencies`가 있으면 호출해 번들 런타임을 먼저 확보한다. 명령 PATH에 없는 실제 실행 파일의 상위 폴더를 아래 `-RuntimeBin`에 전달할 수 있다. 이 문서의 사용자별 경로를 다른 PC에 하드코딩하지 않는다.
3. Windows에서는 스킬의 **절대 경로**로 아래를 실행한다. `-Apply`가 빠지면 읽기 전용 점검이다. 보고서는 현재 작업 산출물 폴더에 둔다.

```powershell
& '<스킬 절대경로>\scripts\bootstrap_windows.ps1' -Apply -Report '<산출물 절대경로>\exam-environment.json'
# 번들 실행 파일 폴더가 필요한 경우:
# -RuntimeBin @('<Python 폴더>','<Node 폴더>','<Git cmd 폴더>')
```

4. `status=READY`와 `editor_smoke.status=PASS`를 확인한다. 파일 존재만으로 설치 성공을 판단하지 않는다. 새 HWPX 스킬을 설치했으면 실제 경로의 `SKILL.md`를 읽어 이번 작업에도 적용하고, “설치한 스킬은 다음 턴부터 자동 검색됩니다”라고 안내한다. 요청한 작업은 이번 턴에 계속한다.
5. 결과의 `hancom` 목록과 Computer Use의 현재 `sky.list_apps()`/`sky.list_windows()`를 대조하여 실제 한글로 바로 이어간다. `native_layout_status=AVAILABLE_NOT_YET_VERIFIED`는 설치된 한글을 찾았다는 뜻이며, 문서 조판 합격이라는 뜻이 아니다.

## 자동 처리 범위

- HWPX 에디터는 [imsebeom/hwpx](https://github.com/imsebeom/hwpx)의 검증한 커밋 `abea249f05f4982a40bc56adf765ea5d32538c82`을 사용한다. Codex 내장 skill-installer의 `install-skill-from-github.py --path . --name hwpx`를 호출한다. 사용자 스킬 폴더는 `CODEX_HOME/skills`, 미설정 시 `~/.codex/skills`이다. 외부 문서의 Claude 전용 환경 변수는 Codex 경로로 바꿔 해석한다.
- 이미 있는 `hwpx`는 pull·덮어쓰지 않는다. 필수 파일이 없는 기존 폴더는 손상/다른 버전으로 보고 그대로 보존하고 원인을 알린다. 사용자 커스텀 스킬을 자동으로 삭제하거나 대체하지 않는다.
- 실행 가능한 Git, Node.js22.12 이상 및 npm, Python3.10 이상을 확인한다. Windows에서 없으면 WinGet의 정확한 ID `Git.Git`, `OpenJS.NodeJS.LTS`, `Python.Python.3.12`로 설치하고 실행을 재검사한다. 시스템 PATH를 덮어쓰지 않는다. 이미 작동하는 도구의 최신 버전 업데이트를 강요하지 않는다.
- HWPX/XML/PDF 검증에 필요한 `lxml`, `python-hwpx`, `PyMuPDF`, `Pillow`가 없으면 `CODEX_HOME/cache/exam-maker/python`의 격리 환경에 설치한다. 그 후 보고서의 `python` 경로를 검증 스크립트 실행에 사용한다.
- 에디터 빌드가 없으면 `node <hwpx>/editor/setup.mjs`를1회 실행한다. Git으로 rhwp 소스를 받고 npm으로 의존성 및 WASM을 준비한다. Rust는 필수가 아니다. 빌드 파일과 엔진의 실제 초기화·빈 HWPX 파싱까지 검사한다. UI 서버를 임의로 띄우거나 사용자의 열린 문서를 바꾸는 과정은 설치 점검에 포함하지 않는다.
- 한글을 쓰는 이 Windows 시험지 작업은 **Computer Use → 한글**이 기본 편집 경로다. rhwp 에디터 설치 때문에 최종 시험지를 rhwp로 재저장하지 않는다. Mac/한글 미설치 시에는 rhwp가 대체 편집 수단이며, 한글 조판 검증은 미완료로 남긴다.

## 한글 버전·제품 이름 자동 탐색

앱 이름에 ‘한글2024’라는 고정 문자열을 요구하지 않는다. 다음을 함께 확인한다.

- Computer Use의 실행 중 앱/설치 앱 목록
- Windows32/64비트 레지스트리의 Hwp.exe App Paths, HWPFrame COM 등록 경로
- 설치 제품의 DisplayIcon·InstallLocation(한컴오피스, 한글, Hancom 등)
- Program Files 양쪽과 사용자 Programs의 Hnc/Hancom/한글/한컴 설치 폴더

실제 존재하는 **Hwp.exe**만 후보로 인정하고 뷰어·한셀을 제외한다. COM 등록 경로를 우선하며 여러 버전이면 모두 보고한다. 사용자가 이미 작업 중인 한글 창이 있으면 그 버전을 우선한다. 필요하면 결과의 `app` 값(`process:<실제 Hwp.exe 경로>`)을 `sky.launch_app`에 전달하고 새 창을 재조회한다. 경로에 한글이나 공백이 있어도 문자열 인자로 전달한다. 한글2020/2024의 메뉴·단축키 차이는 실제 화면으로 확인한다.

한글 자체는 유료 제품이므로 이 부트스트랩이 구매·인증하거나 임의 설치하지 않는다. 한글을 찾지 못하면 HWPX 에디터 경로로 작업을 진행하면서 네이티브 최종 검증이 남았다고 알린다.

## 제한·실패 처리

WinGet 미설치·네트워크 차단·관리자 정책·UAC가 설치를 막으면 오류를 숨기지 않는다. 우선 Codex 번들 런타임을 사용하고, 해결되지 않으면 정확한 누락 항목을 안내한다. 실행 정책·보안 해시 검사·조직 정책을 끄지 않는다. HWPX 설치 스크립트가 없으면 Codex의 실제 skill-installer 위치를 찾아 `--installer`로 전달한다. 설치 서버나 다운로드 주소를 추측하지 않는다.

Mac에서는 `bootstrap_exam.py --apply`로 이미 존재하는 런타임을 이용한 스킬 설치·빌드는 가능하지만, Windows WinGet 설치 분기는 실행되지 않는다. 필요한 런타임이 없다면 설치된 패키지 관리자/공식 설치 경로를 확인한다. 이번 Windows 검증을 Mac 실기 검증으로 표시하지 않는다.

## 근거

- [Codex 스킬 작성 안내](https://developers.openai.com/plugins/build/skills)
- [WinGet install 공식 옵션](https://learn.microsoft.com/en-us/windows/package-manager/winget/install)
- [Git for Windows 공식 설치](https://git-scm.com/install/windows)
- [Node.js 공식 배포](https://nodejs.org/en/download)

검증 결과는 [환경 준비 테스트 기록](environment-bootstrap-test-results.md)에 둔다.
