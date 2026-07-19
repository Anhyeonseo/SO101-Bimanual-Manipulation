# 검증 매트릭스

상태: `NOT RUN`, `PASS`, `FAIL`, `BLOCKED`

| ID | 단계 | 검증 | 초기 합격 기준 | 상태 | 증거 |
|---|---|---|---|---|---|
| HW-001 | Phase 0 | 서보 12개 ping | 12/12 응답 | NOT RUN |  |
| HW-002 | Phase 0 | ID-관절 매핑 | 좌우 각 1~6 기록 | NOT RUN |  |
| HW-003 | Phase 0 | feedback read | position/speed/load/voltage 기록 | NOT RUN |  |
| HW-004 | Phase 0 | 전원 재인가 | 비명령 동작 0회 | NOT RUN |  |
| HW-005 | Phase 0 | 전원 출력 | 양팔 각 무부하/동작 전압 기록 | NOT RUN |  |
| ROS-001 | Phase 1 | fresh build | 오류 0 | NOT RUN |  |
| ROS-002 | Phase 1 | Mock launch | STANDBY 진입 | NOT RUN |  |
| ROS-003 | Phase 1 | invalid command | NaN/limit/stale 100% 거부 | NOT RUN |  |
| MCU-001 | Phase 2 | packet parser | 절단/CRC/길이 오류 거부 | NOT RUN |  |
| MCU-002 | Phase 2 | heartbeat loss | 정의된 시간 내 감속 정지 | NOT RUN |  |
| MCU-003 | Phase 2 | control loop | overrun/underflow 0 | NOT RUN |  |
| MCU-004 | Phase 2 | dual apply tick | 명령 시작 차이 1 tick 이하 | NOT RUN |  |
| CAM-001 | Phase 3 | 3-camera capture | 장치별 목표 FPS 기록 | NOT RUN |  |
| CAM-002 | Phase 3 | reconnect | 자동 복구 시간 기록 | NOT RUN |  |
| CAM-003 | Phase 3 | control isolation | camera 부하 중 heartbeat 위반 0 | NOT RUN |  |
| CAM-004 | Phase 3 | inference schedule | 모든 phase 합계 12Hz 이하 | NOT RUN | `config/camera_schedule.json` |
| CAM-005 | Phase 3 | frame freshness | phase별 p95/max 기록 | NOT RUN |  |
| RES-001 | Phase 3/9 | Pi resource budget | CPU/memory/temperature 기준 충족 | NOT RUN |  |
| POL-001 | Phase 11 | structured policy runtime | raw image 입력 없음, deadline 기록 | NOT RUN |  |
| MOT-001 | Phase 5 | 오른팔 trajectory | 반복 실행 성공 | NOT RUN |  |
| MOT-002 | Phase 5 | cancel/stop | 정해진 안전 상태 진입 | NOT RUN |  |
| VIS-001 | Phase 6 | table localization | grasp 허용 오차 이내 | NOT RUN |  |
| TASK-001 | Phase 7 | Pick | 50회 중 90% 이상 | NOT RUN |  |
| TASK-002 | Phase 7 | Place | 50회 중 90% 이상 | NOT RUN |  |
| SYS-001 | Phase 9 | boot | 반복 부팅 모두 무동작 STANDBY | NOT RUN |  |
| SYS-002 | Phase 9 | soak | 8시간 후 24시간 | NOT RUN |  |
| DUAL-001 | Phase 10 | physical start skew | 측정값과 기준 기록 | NOT RUN |  |
| DUAL-002 | Phase 10 | coordinated stop | 한 팔 fault 시 양팔 정지 | NOT RUN |  |
| AI-001 | Phase 11 | policy comparison | baseline 대비 개선 | NOT RUN |  |

초기 합격 기준은 Phase 0 측정과 위험 분석 후 조정할 수 있다. 기준을 변경하면 ADR 또는 변경 사유를 남긴다.
