# ~/prewoos/schedule_run_all.sh
#!/usr/bin/env bash
# 하루에 5번 random time 에 run_all 예약하기

# 사용할 명령어와 환경 준비
BASE_DIR="/home/prewoos2018/prewoos"
VENV_ACT="$BASE_DIR/venv/bin/activate"
SCRIPT_CMD="source $VENV_ACT && export CHROME_HEADLESS=true && python3 -m scripts.run_all"

# 예약할 시간대 범위 설정 (예: 09:00 ~ 21:00 사이)
START_HOUR=9
END_HOUR=21

for i in $(seq 1 5); do
  # 1) 랜덤 시(정수) 생성
  HOUR=$(shuf -i ${START_HOUR}-${END_HOUR} -n 1)
  # 2) 랜덤 분(0~59) 생성
  MIN=$(shuf -i 0-59 -n 1)
  # 3) at에 넘길 시각 포맷 (HH:MM)
  TIME=$(printf "%02d:%02d" "$HOUR" "$MIN")
  echo "예약 #$i → $TIME 에 실행"
  # 4) at 명령으로 예약
  echo "$SCRIPT_CMD" | at "$TIME"
done
