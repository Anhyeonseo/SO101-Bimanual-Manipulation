# 하드웨어 인벤토리

상태 표기: `확정`, `측정 필요`, `미정`

## 컴퓨팅

| 항목 | 값 | 상태 | 증거/비고 |
|---|---|---|---|
| Main SBC | Raspberry Pi 5 4GB | 확정 | 실제 보유 |
| SBC OS | Ubuntu Server 24.04 | 확정 | 설치 완료 |
| ROS | ROS 2 Jazzy | 확정 | 설치 완료 |
| Pi 전원 | 공식 27W USB-C | 확정 | 실제 보유 |
| Pi 냉각 | 외부 선풍기 | 확정 | 장시간 시험 전 능동 냉각 재검토 |
| Pi 저장장치 | microSD | 확정 | journald/rosbag 쓰기량 제한 필요 |
| 개발 PC | Windows 11 / Ubuntu 24.04 dual boot | 확정 | RTX 5070 Ti |

## 로봇팔과 서보

| 항목 | 값 | 상태 | 증거/비고 |
|---|---|---|---|
| Arm | Stock SO-ARM101 follower × 2 | 확정 | 공식 wrist camera mount 적용 |
| Base 방향 | 양팔 동일 방향 | 확정 |  |
| Base 중심 거리 | 약 14 inch / 355.6 mm | 측정 필요 | 최종 mm 측정 필요 |
| 자세 관절 | 팔당 5개 | 확정 | gripper 제외 |
| Gripper | 팔당 1축 | 확정 |  |
| 장착 서보 | STS3215 12V × 12 | 확정 |  |
| 예비 서보 | STS3215 12V × 2 | 확정 |  |
| 서보 ID | 각 버스 1~6 | 측정 필요 | 관절 매핑 확인 필요 |
| Joint zero/direction | 미기록 | 측정 필요 | Phase 0 |
| Raw position range | 미기록 | 측정 필요 | Phase 0 |
| Feedback 항목 | position/speed/load/voltage 예상 | 측정 필요 | 실제 read 검증 필요 |

## 전원과 서보 버스

| 항목 | 값 | 상태 | 증거/비고 |
|---|---|---|---|
| 왼팔 전원 | 12V 10A | 확정 | 실제 출력 전압 측정 필요 |
| 오른팔 전원 | 12V 10A | 확정 | 실제 출력 전압 측정 필요 |
| 서보 전원 분리 | 좌우 독립 | 확정 |  |
| Servo adapter | Waveshare Bus Servo Adapter (A) × 2 | 확정 | UART/USB 지원형 |
| Servo bus | 좌우 독립 | 확정 | ID 중복 허용, arm namespace 필수 |
| 물리 E-stop | 없음 | 미정 | 자동 작업 전 추가 권장, 양팔 단계 전 필수 검토 |
| 분기 퓨즈 | 확인 안 됨 | 측정 필요 | 배선 사진과 정격 기록 필요 |
| Ground topology | 확인 안 됨 | 측정 필요 | Pi/STM32/좌우 adapter 기준 전위 문서화 |

## MCU

| 항목 | 값 | 상태 | 증거/비고 |
|---|---|---|---|
| Board | NUCLEO-G474RE | 확정 |  |
| Pi link | On-board ST-LINK VCP | 확정 | udev 식별값 확인 필요 |
| RTOS | FreeRTOS | 확정 | 신규 펌웨어 작성 |
| Left servo link | 독립 UART 예정 | 측정 필요 | CubeMX 핀 배치 필요 |
| Right servo link | 독립 UART 예정 | 측정 필요 | CubeMX 핀 배치 필요 |
| Existing firmware | 없음 | 확정 |  |

## 카메라

| 위치 | 장치 | 상태 | 확인할 항목 |
|---|---|---|---|
| Top | XPCAM HD 1080p USB webcam | 확정 | VID/PID, serial, UVC format, focus, exposure |
| Left wrist | Innomaker 1080p USB 2.0 UVC | 확정 | VID/PID, serial, UVC format, focus, exposure |
| Right wrist | Innomaker 1080p USB 2.0 UVC | 확정 | VID/PID, serial, UVC format, focus, exposure |
| USB hub | USB 3.0 powered hub, 5V 3A | 확정 | topology, back-power, 3-camera stability |

## 작업 환경

| 항목 | 값 | 상태 |
|---|---|---|
| 첫 물체 | 검은색 마커펜 | 확정 |
| 목적지 | 펜꽂이 | 확정 |
| 조명 | 고정 환경 | 확정 |
| 작업대 크기/높이 | 미기록 | 측정 필요 |
| 펜 크기 | 미기록 | 측정 필요 |
| 펜꽂이 입구 | 미기록 | 측정 필요 |

