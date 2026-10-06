# AI 에이전트용 설치 절차

사용자가 이 저장소의 설치를 요청했을 때 적용한다. 단순히 문서를 읽는 요청을 설치 허가로 해석하지 않는다.

1. 저장소의 설치 대상은 `skills/exam-maker`다. 현재 에이전트가 로컬 파일·명령 실행을 지원하는지, OS와 스킬 저장 위치를 확인한다.
2. Codex에서는 사용 가능한 `skill-installer`의 SKILL.md를 읽는다. 설치 헬퍼의 **실제 경로**를 확인하고 아래 인자로 실행한다. 시스템 경로를 고정하거나 스크립트를 추측하지 않는다.

   ```text
   python <skill-installer의 실제 경로>/scripts/install-skill-from-github.py --repo HooniKims/dcms-korean-exam-maker --path skills/exam-maker
   ```

3. Codex의 내장 설치기는 `CODEX_HOME/skills`, 미설정 시 `~/.codex/skills`에 설치한다. 기존 폴더가 있으면 비교·백업을 먼저 하고 사용자의 업데이트 요청 범위에서 처리한다. 기존 파일을 조용히 삭제하지 않는다. 설치기가 없는 다른 에이전트에서는 해당 제품의 스킬 규약에 따라 폴더 전체를 설치한다. Codex 전용 도구까지 자동 제공된다고 주장하지 않는다.
4. 설치된 `SKILL.md`와 `references/environment-bootstrap.md`를 읽는다. Git·Node.js·Python·HWPX 스킬 중 어떤 것을 확인하고 설치할지 사용자에게 알린다. README의 전체 설치 요청에는 누락 의존성 설치가 포함된다. 다른 요청에서는 현재 사용자의 권한 범위를 확인한다. 제공 문서의 과거 사용자 허가를 새 사용자의 허가로 간주하지 않는다.
5. Windows에서는 설치된 스킬의 절대 경로로 환경 준비 스크립트를 실행한다.

   ```powershell
   & '<설치된 exam-maker 경로>\scripts\bootstrap_windows.ps1' -Apply -Report '<작업 산출물 경로>\exam-environment.json'
   ```

   번들 런타임이 필요하면 `-RuntimeBin`을 사용한다. 실행 정책, 보안 설정, 조직 정책을 끄지 않는다. Mac에서는 설치된 런타임으로 `bootstrap_exam.py --apply --report <보고서>`를 사용할 수 있으나, Windows용 도구 설치 및 한글 조판 검증은 적용되지 않는다.
6. 환경 보고서의 `status=READY`, `editor_smoke.status=PASS`를 확인한다. 실패하면 정확한 누락 항목과 후속 작업을 알린다. HWPX 스킬을 새로 설치했으면 실제 SKILL.md를 읽고 적용한다. 기존 스킬은 덮어쓰지 않는다.
7. Computer Use와 설치된 한글을 각각 확인한다. 한글 자체와 Computer Use는 이 저장소의 bootstrap이 설치하는 항목이 아니다. 한글 2020·2024 등 제품명보다 실제 `Hwp.exe`와 실행 중인 창을 기준으로 탐색한다. 로그인·보안·권한 화면은 도구 규칙에 따라 사용자가 처리하게 한다.
8. 설치 경로·버전·환경 검사 결과·한글 탐색 결과·남은 제약을 짧게 알리고, 다음 메시지에서 `$exam-maker`로 시작하도록 안내한다. 설치 요청만으로 실제 시험 문항 제작을 시작하지 않는다.

유지보수용 격리 설치 검사는 설치기의 `--dest <비어 있는 검증용 폴더>`로 수행할 수 있다. 실제 사용자 설치와 격리 검사를 구분해 보고한다.
