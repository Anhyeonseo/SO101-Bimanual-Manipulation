# 검증 매트릭스

상태: `미실행`, `부분 통과`, `통과`, `실패`, `차단`

| ID | 단계 | 검증 | 초기 합격 기준 | 상태 | 증거 |
|---|---|---|---|---|---|
| HW-001 | 단계 0 | 서보 12개 ping | 12/12 응답 | 부분 통과 | 단일 시험 팔 6/6 응답 |
| HW-002 | 단계 0 | ID와 관절 연결 확인 | 좌우 각 1~6 기록 | 부분 통과 | 단일 시험 팔 ID 1~6 확인 |
| HW-003 | 단계 0 | 상태값 읽기 | position/speed/load/voltage 기록 | 부분 통과 | [단일 팔 실기 결과](test-results/2026-07-20-stm32-binary-control-plane.md) |
| HW-004 | 단계 0 | 전원 재인가 | 명령하지 않은 움직임 0회 | 부분 통과 | 단일 시험 팔 확인 |
| HW-005 | 단계 0 | 전원 출력 | 양팔 각각 무부하/동작 전압 기록 | 부분 통과 | 단일 시험 팔 12.3~12.5V 확인 |
| ROS-001 | 단계 1 | 새 환경 build | 오류 0 | 미실행 |  |
| ROS-002 | 단계 1 | Mock 실행 | STANDBY 진입 | 미실행 |  |
| ROS-003 | 단계 1 | 잘못된 명령 | NaN/범위 초과/오래된 명령 100% 거부 | 미실행 |  |
| MCU-001 | 단계 2 | packet 해석기 | 절단/CRC/길이 오류 거부 | 통과 | [바이너리 제어 경로 결과](test-results/2026-07-20-stm32-binary-control-plane.md) |
| MCU-002 | 단계 2 | heartbeat 단절 | 정의된 시간 안에 안전 정지 | 통과 | [바이너리 제어 경로 결과](test-results/2026-07-20-stm32-binary-control-plane.md) |
| MCU-003 | 단계 2 | 제어 loop | overrun/underflow 0 | 미실행 | 여러 sample queue 구현 후 시험 |
| MCU-004 | 단계 2 | 단일 팔 6축 동시 적용 | 같은 명령에서 함께 시작 | 통과 | [바이너리 제어 경로 결과](test-results/2026-07-20-stm32-binary-control-plane.md) |
| CAM-001 | 단계 3 | 카메라 3대 capture | 장치별 목표 FPS 기록 | 미실행 |  |
| CAM-002 | 단계 3 | 재연결 | 자동 복구 시간 기록 | 미실행 |  |
| CAM-003 | 단계 3 | 제어 격리 | 카메라 부하 중 heartbeat 위반 0 | 미실행 |  |
| CAM-004 | 단계 3 | 추론 일정 | 모든 작업 상태 합계 12Hz 이하 | 통과 | `config/camera_schedule.json` 정적 검증 |
| CAM-005 | 단계 3 | frame 최신성 | 상태별 p95/max 기록 | 미실행 |  |
| RES-001 | 단계 3/9 | Pi 자원 한도 | CPU/memory/temperature 기준 충족 | 미실행 |  |
| POL-001 | 단계 11 | structured policy 실행 | raw image 입력 없음, deadline 기록 | 미실행 |  |
| MOT-001 | 단계 5 | 오른팔 trajectory | 반복 실행 성공 | 통과 | [6축 OUT/HOME 결과](test-results/2026-07-20-stm32-binary-control-plane.md) |
| MOT-002 | 단계 5 | 취소/정지 | 정해진 안전 상태 진입 | 통과 | [이동 중 SAFE_STOP 결과](test-results/2026-07-20-stm32-binary-control-plane.md) |
| VIS-001 | 단계 6 | 작업대 위치 추정 | grasp 허용 오차 이내 | 미실행 |  |
| TASK-001 | 단계 7 | Pick | 50회 중 90% 이상 | 미실행 |  |
| TASK-002 | 단계 7 | Place | 50회 중 90% 이상 | 미실행 |  |
| SYS-001 | 단계 9 | 부팅 | 반복 부팅 모두 무동작 STANDBY | 미실행 |  |
| SYS-002 | 단계 9 | 장시간 시험 | 8시간 후 24시간 | 미실행 |  |
| DUAL-001 | 단계 10 | 실제 시작 시각 차이 | 측정값과 기준 기록 | 미실행 |  |
| DUAL-002 | 단계 10 | 연동 정지 | 한 팔 fault 시 양팔 정지 | 미실행 |  |
| AI-001 | 단계 11 | policy 비교 | baseline 대비 개선 | 미실행 |  |

`부분 통과`는 현재 단일 시험 팔에서는 확인했지만 양팔 전체 기준은 아직 충족하지 않았다는 뜻이다. 초기 합격 기준은 단계 0 측정과 위험 분석 후 조정할 수 있으며, 기준을 바꾸면 ADR 또는 변경 사유를 남긴다.
