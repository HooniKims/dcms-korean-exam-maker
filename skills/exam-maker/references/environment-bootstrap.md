# 환경에 따른 한글·에디터 선택

사용자 최종 지정(2026-10-07): **무조건 에디터를 설치하지 않는다. Windows에 한글이 있으면 한글을 직접 사용하고, Mac에 한글이 없으면 에디터를 설치하여 확인한다.** 이 지정은 10월5일의 무조건 에디터 준비 기본값을 대체한다. 이미 설치된 에디터나 사용자 커스텀 스킬은 삭제하지 않는다.

## 첫 단계: 운영체제와 한글부터 확인

1. OS, 설치된 한글 앱, 에이전트의 실제 Computer Use 기능을 확인한다. “운영체제와 한글 설치 여부를 확인한 뒤 필요한 구성요소만 준비하겠습니다.”라고 알린다. 설명·스킬 유지보수 요청에는 설치나 앱 실행이 필요 없다.
2. **Windows + 한글:** Computer Use로 한글 작업 사본을 열어 수정·저장·PDF 출력·검수한다. rhwp 에디터 설치·빌드·스모크 검사·실행을 모두 생략한다. Git·Node·Python을 에디터 때문에 설치하지 않는다. 이미 설치된 HWPX 스킬에서 ‘결과를 항상 별도 에디터로 열기’를 요구해도 이 사용자의 한글 우선 결정이 우선이다.
3. **Mac + 한글 없음:** HWPX 에디터를 설치하거나 기존 설치를 재사용하고, 실제 문서를 열어 표시를 확인한다. 에디터 화면 검수를 한글 조판 합격으로 표시하지 않는다.
4. **Mac + 한글 있음:** 설치 앱과 지원되는 네이티브 제어를 우선 확인한다. Windows 전용 Computer Use/COM을 호출하지 않는다. Windows에서 한글이 없는 경우에도 에디터 대체 경로를 사용할 수 있다. 한글 UI의 일시적인 실패는 미설치가 아니므로 에디터를 자동 추가하지 않는다.
5. XML/PDF 검사가 실제로 필요하면 번들 런타임(`load_workspace_dependencies`)이나 기존 Python과 필요한 라이브러리를 사용한다. 한글 직접 조작의 선행 설치 조건으로 만들지 않는다.

## 환경 보고서

```powershell
& '<스킬 절대경로>\scripts\bootstrap_windows.ps1' -Apply -Report '<산출물 절대경로>\exam-environment.json'
# 에디터 경로에서 필요한 번들 런타임: -RuntimeBin @('<Python 폴더>','<Node 폴더>','<Git cmd 폴더>')
```

Windows 시작 스크립트는 레지스트리·설치 폴더·실행 중 앱에서 한글을 먼저 찾는다. 한글을 찾으면 **Python을 찾거나 설치하기 전에 종료**한다. Python 직접 진입점 `bootstrap_exam.py`도 한글 검색 직후 같은 네이티브 분기를 적용한다.

- 네이티브 경로: `workflow=hancom`, `status=READY`, `editor_required=false`, `editor_smoke.status=SKIPPED_NATIVE`, `actions=[]`. Computer Use 지원은 에이전트에서 따로 확인한다. `native_layout_status=AVAILABLE_NOT_YET_VERIFIED`는 앱 발견일 뿐 문서 검수 합격이 아니다.
- 에디터 경로: `workflow=editor`이며 아래 필요한 항목을 준비한다. `status=READY`와 `editor_smoke.status=PASS`를 확인한다. 파일 존재만으로 성공을 판단하지 않는다.
- 사용자가 한글이 있어도 에디터를 명시적으로 요청한 경우에만 `-Editor` / `--editor`를 사용한다. 일반 HWPX 스킬 지침이나 UI 실패를 그 요청으로 간주하지 않는다.

Mac에서 한글이 없을 때는 번들/기존 Python으로 `python bootstrap_exam.py --apply --report <보고서>`를 실행한다. `--apply`가 없으면 읽기 전용 점검이다. 현재 사용자의 설치 허가는 이어 적용하되, 문서 속 과거 동의를 다른 사용자의 허가로 해석하지 않는다.

## 에디터 경로에서만 준비하는 항목

- HWPX 에디터는 [imsebeom/hwpx](https://github.com/imsebeom/hwpx)의 지정 커밋 `abea249f05f4982a40bc56adf765ea5d32538c82`을 사용한다. 실제 Codex skill-installer 경로로 `--path . --name hwpx`를 실행한다. 설치 위치는 `CODEX_HOME/skills`, 미설정 시 `~/.codex/skills`다. 새 설치의 SKILL.md를 읽고 작업을 이어 간다.
- 이미 있는 hwpx는 pull·덮어쓰지 않는다. 기존 에디터가 손상됐어도 한글 네이티브 경로를 막지 않는다. 에디터 경로에서만 누락 파일을 진단한다.
- Git, Node.js22.12 이상/npm, Python3.10 이상을 확인한다. 번들·기존 런타임을 먼저 사용한다. Windows 에디터 대체 경로에서만 누락 도구를 WinGet의 정확한 ID로 설치한다. Mac의 누락 런타임은 해당 플랫폼에서 사용 가능한 설치 수단을 확인하고 처리한다. 정상 도구의 업데이트를 강요하지 않는다.
- 필요한 `lxml`, `python-hwpx`, `PyMuPDF`, `Pillow`는 격리 환경 `CODEX_HOME/cache/exam-maker/python`에 준비한다.
- 에디터 빌드가 없으면 `node <hwpx>/editor/setup.mjs`를 실행한다. Git으로 소스, npm으로 의존성/WASM을 준비하고 실제 엔진 초기화·빈 HWPX 파싱을 확인한다. 설치 점검 자체가 사용자의 열린 문서를 바꾸지는 않는다. 이후 편집 작업에서 실제 파일을 열어 확인한다.

## 한글 버전·제품 이름 자동 탐색

앱 이름에 ‘한글2024’라는 고정 문자열을 요구하지 않는다. 다음을 함께 확인한다.

- Computer Use의 실행 중 앱/설치 앱 목록
- Windows32/64비트 레지스트리의 Hwp.exe App Paths, HWPFrame COM 등록 경로
- 설치 제품의 DisplayIcon·InstallLocation(한컴오피스, 한글, Hancom 등)
- Program Files 양쪽과 사용자 Programs의 Hnc/Hancom/한글/한컴 설치 폴더

실제 존재하는 **Hwp.exe**만 후보로 인정하고 뷰어·한셀을 제외한다. COM 등록 경로를 우선하며 여러 버전이면 모두 보고한다. 사용자가 이미 작업 중인 한글 창이 있으면 그 버전을 우선한다. 필요하면 결과의 `app` 값(`process:<실제 Hwp.exe 경로>`)을 `sky.launch_app`에 전달하고 새 창을 재조회한다. 경로에 한글이나 공백이 있어도 문자열 인자로 전달한다. 한글2020/2024의 메뉴·단축키 차이는 실제 화면으로 확인한다.

macOS는 `/Applications`와 `~/Applications`의 한글/Hanword 앱 번들에서 Info.plist와 실제 실행 파일을 확인한다. 뷰어·한셀·이름만 있는 빈 앱은 제외한다. 앱 목록과 대조하고, 자동 검색이 놓친 앱은 확인된 실제 앱을 우선한다.

한글 자체는 이 부트스트랩이 구매·인증하거나 임의 설치하지 않는다. 한글 미설치 시 에디터 경로를 사용하며, 에디터 확인을 한글 네이티브 최종 검증으로 보고하지 않는다.

## 제한·실패 처리

WinGet 미설치·네트워크 차단·관리자 정책·UAC가 설치를 막으면 오류를 숨기지 않는다. 우선 Codex 번들 런타임을 사용하고, 해결되지 않으면 정확한 누락 항목을 안내한다. 실행 정책·보안 해시 검사·조직 정책을 끄지 않는다. HWPX 설치 스크립트가 없으면 Codex의 실제 skill-installer 위치를 찾아 `--installer`로 전달한다. 설치 서버나 다운로드 주소를 추측하지 않는다.

Mac에서는 `bootstrap_exam.py --apply`로 이미 존재하는 런타임을 이용한 스킬 설치·빌드는 가능하지만, Windows WinGet 설치 분기는 실행되지 않는다. 필요한 런타임이 없다면 설치된 패키지 관리자/공식 설치 경로를 확인한다. 이번 Windows 검증을 Mac 실기 검증으로 표시하지 않는다.

## 근거

- [Codex 스킬 작성 안내](https://developers.openai.com/plugins/build/skills)
- [WinGet install 공식 옵션](https://learn.microsoft.com/en-us/windows/package-manager/winget/install)
- [Git for Windows 공식 설치](https://git-scm.com/install/windows)
- [Node.js 공식 배포](https://nodejs.org/en/download)

검증 결과는 [환경 준비 테스트 기록](environment-bootstrap-test-results.md)에 둔다.
