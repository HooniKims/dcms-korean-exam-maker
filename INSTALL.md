# AI 에이전트용 설치 절차

사용자가 이 저장소의 설치를 요청했을 때 적용한다. 단순히 문서를 읽는 요청을 설치 허가로 해석하지 않는다.

1. 저장소의 설치 대상은 `skills/exam-maker`다. 현재 에이전트가 로컬 파일·명령 실행을 지원하는지, OS와 스킬 저장 위치를 확인한다.
2. Codex에서는 사용 가능한 `skill-installer`의 SKILL.md를 읽는다. 설치 헬퍼의 **실제 경로**를 확인하고 아래 인자로 실행한다. 시스템 경로를 고정하거나 스크립트를 추측하지 않는다.

   ```text
   python <skill-installer의 실제 경로>/scripts/install-skill-from-github.py --repo HooniKims/dcms-korean-exam-maker --path skills/exam-maker
   ```

3. Codex의 내장 설치기는 `CODEX_HOME/skills`, 미설정 시 `~/.codex/skills`에 설치한다. 기존 폴더가 있으면 비교·백업을 먼저 하고 사용자의 업데이트 요청 범위에서 처리한다. 기존 파일을 조용히 삭제하지 않는다. 설치기가 없는 다른 에이전트에서는 해당 제품의 스킬 규약에 따라 폴더 전체를 설치한다. Codex 전용 도구까지 자동 제공된다고 주장하지 않는다.
4. 설치된 `SKILL.md`와 `references/environment-bootstrap.md`를 읽고 **OS와 한글 설치 여부부터** 확인한다. Windows에 한글이 있으면 Computer Use로 바로 진행하며 HWPX 에디터·Git·Node.js를 설치하지 않는다. Python도 직접 한글 조작의 필수 설치가 아니다. 필요한 구조 검사를 실행할 때만 번들/기존 런타임을 우선한다. 기존 스킬이나 에디터는 삭제하지 않는다.
5. Windows 환경 보고서는 아래 스크립트로 만들 수 있다. 한글을 찾으면 Python 유무와 관계없이 네이티브 경로를 보고하고 설치 단계 전에 끝난다.

   ```powershell
   & '<설치된 exam-maker 경로>\scripts\bootstrap_windows.ps1' -Apply -Report '<작업 산출물 경로>\exam-environment.json'
   ```

   `workflow=hancom`, `editor_required=false`, `editor_smoke.status=SKIPPED_NATIVE`이면 에디터 검사 실패가 아니다. Computer Use 제공 여부를 별도로 확인한다. 한글 설치 확인은 문서 조판 검증 완료가 아니다.
6. **Mac에 한글이 없으면** 번들/기존 Python으로 `bootstrap_exam.py --apply --report <보고서>`를 실행하여 HWPX 에디터를 설치·빌드하고 실제 문서를 열어 확인한다. Mac에서도 한글 앱을 찾으면 네이티브 경로를 보고하며 에디터 설치를 생략한다. `workflow=editor`에서만 `status=READY`, `editor_smoke.status=PASS`를 요구한다. 필요한 Git/Node가 없으면 실제 플랫폼의 설치 수단을 확인하며 Windows WinGet/COM을 Mac에서 실행하지 않는다. 네이티브 검수와 에디터 검수를 구별한다.
7. 사용자에게 필요한 항목만 알리고 승인된 범위에서 설치한다. Windows에 한글이 없는 경우에도 에디터 대체 경로를 사용할 수 있다. 한글이나 Computer Use 자체는 이 저장소가 설치하지 않는다. 한글의 일시적 UI 오류만으로 에디터 설치를 시작하지 않는다. 사용자가 명시적으로 별도 에디터를 요청한 경우에만 `-Editor` / `--editor`로 네이티브 우선을 재정의한다. 로그인·보안·권한 화면은 도구 규칙을 따른다.
8. 설치 경로·버전·환경 검사 결과·한글 탐색 결과·남은 제약을 짧게 알리고, 다음 메시지에서 `$exam-maker`로 시작하도록 안내한다. 설치 요청만으로 실제 시험 문항 제작을 시작하지 않는다.

유지보수용 격리 설치 검사는 설치기의 `--dest <비어 있는 검증용 폴더>`로 수행할 수 있다. 실제 사용자 설치와 격리 검사를 구분해 보고한다.
