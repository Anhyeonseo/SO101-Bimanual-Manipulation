# 포트폴리오 작업 기록

이 파일은 결과만 나열하지 않고 문제, 판단, 검증과 개선 과정을 기록한다.

## 기록 템플릿

### YYYY-MM-DD — 작업 제목

**목표**

- 이번 작업에서 확인하려는 내용

**구현/시험**

- 변경한 파일, 하드웨어 구성, 실행한 명령

**측정 결과**

| 지표 | 결과 | 조건 |
|---|---|---|
| 예시 |  |  |

**문제와 원인**

- 관찰된 증상
- 확인한 원인

**설계 판단**

- 채택한 방식
- 대안과 채택하지 않은 이유

**증거**

- 로그, 그래프, 사진, 영상, benchmark 결과 경로

**완료 판정**

- PASS/FAIL/BLOCKED
- 다음 단계 진입 가능 여부

---

## 2026-07-12 — 프로젝트 착수 및 Phase 0 정의

**목표**

- 전체 프로젝트를 검증 게이트 방식으로 관리한다.
- 하드웨어, 안전, ROS, 펌웨어, 카메라, 시뮬레이션과 정책 학습의 선행 관계를 명확히 한다.

**구현/시험**

- 프로젝트 헌장 작성
- 하드웨어 인벤토리 작성
- 전체 로드맵 및 검증 매트릭스 작성
- 핵심 아키텍처 ADR 작성

**설계 판단**

- 오른팔 deterministic Pick and Place를 첫 통합 목표로 선택했다.
- 정책 학습 전에 측정 가능한 baseline을 만든다.
- Pi 카메라 성능 검증은 인식 구현보다 먼저 수행한다.
- STM32는 FreeRTOS 기반 실시간 actuator controller로 제한한다.

**완료 판정**

- 문서 생성 후 검토 예정
- 다음 작업: 서보 12축 하드웨어 기준선 기록

---

## 2026-07-12 — Phase 0 측정 데이터 자동 검증

**목표**

- 서보 기준선 측정의 누락과 안전 상태 모순을 자동으로 검출한다.
- 오른팔 우선 측정과 양팔 최종 게이트를 같은 데이터 형식으로 관리한다.

**구현/시험**

- `hardware/phase0_baseline.json` 측정 템플릿 추가
- `tools/validate_phase0.py` fail-closed 검증기 추가
- 정상 데이터, 오른팔 단독, 중복 관절, 비명령 동작, safe range 이탈 테스트 추가

**측정 결과**

| 지표 | 결과 | 조건 |
|---|---|---|
| 단위 테스트 | 5/5 PASS | Python unittest |
| 실제 오른팔 baseline | FAIL, 미입력 70개 | 측정 전 템플릿 |
| whitespace 검사 | PASS | `git diff --check` |

**설계 판단**

- 측정 전 검증 실패를 정상 상태로 취급한다.
- 누락값을 임의 기본값으로 대체하지 않는다.
- 오른팔만 먼저 검증할 수 있지만 전체 Phase 0 완료는 양팔 데이터가 필요하다.

**증거**

- `tests/test_validate_phase0.py`
- `hardware/phase0_baseline.json`
- `tools/validate_phase0.py`

**완료 판정**

- 도구 구현 PASS
- 하드웨어 게이트는 실제 측정 전이므로 NOT RUN 유지

---

## 2026-07-12 — Pi–STM32 protocol contract 초안

**목표**

- 펌웨어와 ROS hardware interface를 작성하기 전에 wire protocol의 책임, framing, 단위, 상태와 메시지 ID를 고정한다.

**구현/시험**

- COBS + CRC-32C 기반 frame layout 제안
- little-endian fixed-width integer와 micro-radian 단위 정의
- common `apply_tick` 기반 좌우 setpoint 원자성 정의
- session/state/motion/feedback message ID manifest 작성
- 중복 ID, reserved range, 필수 메시지, 잘못된 `ESTOP` software message 검출 테스트

**측정 결과**

| 지표 | 결과 | 조건 |
|---|---|---|
| 전체 repository unittest | 10/10 PASS | Phase 0 + protocol validator |
| protocol manifest | PASS | 18개 unique message |
| 문법/whitespace | PASS | compileall, git diff --check |

**설계 판단**

- 소프트웨어 정지는 `SAFE_STOP`, 물리 정지는 E-stop으로 명확히 구분했다.
- Pi는 raw servo position이 아닌 joint micro-radian을 전송한다.
- STM32가 calibration과 최종 raw limit을 적용한다.
- timeout, queue, control rate는 실측 전 확정하지 않는다.

**증거**

- `protocol/README.md`
- `protocol/message_ids.json`
- `tools/validate_protocol_manifest.py`
- `tests/test_validate_protocol_manifest.py`

**완료 판정**

- protocol structure 검증 PASS
- ADR-0006은 하드웨어 측정과 사용자 검토 전까지 Proposed

---

## 2026-07-12 — Pi 카메라 역할과 compute budget

**목표**

- 카메라 3대, detector, MoveIt과 향후 policy가 Pi 5 4GB 자원을 무제한 경쟁하지 않도록 phase 기반 budget을 정의한다.

**구현/시험**

- Top/Left Wrist/Right Wrist 역할과 calibration 경계 정의
- compressed latest-frame, 선택적 decode, single inference lane 구조 정의
- 8개 task phase의 decode/inference/policy rate 작성
- 총 vision inference, queue depth, thread 수, raw-image policy 금지 자동 검증

**측정 결과**

| 지표 | 결과 | 조건 |
|---|---|---|
| repository unittest | 15/15 PASS | baseline/protocol/camera validators |
| camera schedule | PASS | 8개 phase |
| 최대 vision inference | 12Hz | DUAL_PRIVATE |
| policy input | structured state | raw image false |

**설계 판단**

- Top은 전역 평면 pose와 결과 확인, Wrist는 마지막 상대 정렬을 담당한다.
- 카메라 연결·capture와 decode·inference rate를 분리한다.
- vision 2 threads, policy 1 thread를 초기 상한으로 두고 실제 affinity는 benchmark 후 결정한다.
- control/safety는 부하 저감 대상에서 제외한다.

**증거**

- `docs/CAMERA_COMPUTE_ARCHITECTURE.md`
- `config/camera_schedule.json`
- `tools/validate_camera_schedule.py`
- `tests/test_validate_camera_schedule.py`

**완료 판정**

- architecture와 static budget 검증 PASS
- 실제 UVC/Pi benchmark 전까지 ADR-0007 Proposed
