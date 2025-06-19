해당 프로그램은 node에서 감지한 정보를 Server로 보내는 프로그램입니다.

Server는 population.py이며
>> python population.py 
를 통해 실행시키면 서버가 실행됩니다.
[ https://iot-final-td9q.onrender.com/ 현재 해당 주소에 배포되어 있습니다. ]

sensor.ino를 LoRa TTGO 모델에 업로드하여 실행시키고 적외선 센서를 두 쌍을 연결시키면 node 세팅은 끝납니다.


해당 node에 센서가 두 개가 있고, 이 센서가 지난 시간을 기반으로 어느 방향으로 지나갔는지 판단합니다.

해당 정보를 Server측에 보내서 node가 있는 장소의 인구수를 업데이트 합니다.

