how does it work:
1. ข้อมูลของ user จะเข้ามาทาง api 
2. api ส่งข้อมูลที่เป็น queue message ไปที่ rabbitmq 
3. rabbitmq ส่งข้อมูลเข้า worker
4. worker เช็คข้อมูล user จาก postgresql และดึงข้อมูลออกมา
5. ส่งข้อมูลที่ดึงมาได้เข้าไปคพนวณ similarity(คำนวณความเหมือนของตัวอักษร) ใน vector database
6. sort ข้อมูลที่ได้จาก vector database  แล้วส่งกลับไปที่ api

how to feed input and get output
การส่งข้อมูลทำได้ 2 รูปแบบดังนี้
1. ใช้ postman ในการช่วยยิง request เข้าไปใน api
2. ใช้ swagger ของ fastapi ในการยิงข้อมูลเข้า api

how to improve in the feaure
1. การคำนวณคะแนนความเหมือน(similarity) ต้องใช้ข้อมูลของ user คนนั้นทั้งหมด (ตอนนี้ยังใช้แค่ข้อมูลที่ส่งมาจาก api เท่านั้น)
2. เปลี่ยนรูปแบบของการรับข้อมูลเป็นการใช้ callback api เนื่องจากมีโอกาสที่ตัวคำนวณจะใช้เวลานานแล้วทำให้ api ที่รอ timeout ได้
3. ดึง config ทั้งหมดเข้าไปใน database เพื่อที่เวลาจะเปลี่ยน config จะได้ไม่ต้องทำการ restart service ทุกรอบ ยกตัวอย่างเช่นการ set ค่า weight ในการคำนวณ ค่าความเหมือน(similarity) จะสามารถเปลี่ยนได้ทุกเมื่อเพียงแค่เปลี่ยน config จาก database และ service ที่คำนวณต้องเข้าไปดึงข้อมูล config ใน database ทุกครั้งก่อนเริ่มทำงาน

how to setup
รันทุก service ขึ้นมาโดยการใช้คำสั่งดังนี้
1. ให้ terminal เข้ามาที่ DSAssignmentDataSet
2. เข้าไปใน api-service folder แล้วรัน ./scripts/start_api_compose.sh ใช้คำสั่งนี้เพื่อ build และ run background ของ API
3. เข้าไปใน postgresql folder แล้วรัน ./scripts/start_postgres_compose.sh ใช้คำสั่งนี้เพื่อ build และ run background ของ postgresql database
4. เข้าไปใน postgresql folder แล้วรัน ./scripts/start_rabbitmq_compose.sh ใช้คำสั่งนี้เพื่อ build และ run background ของ rabbitMQ
5. เข้าไปใน postgresql folder แล้วรัน ./scripts/start_qdrant_compose.sh ใช้คำสั่งนี้เพื่อ build และ run background ของ vector database
6. เข้าไปใน postgresql folder แล้วรัน ./scripts/start_worker_compose.sh ใช้คำสั่งนี้เพื่อ build และ run background ของ worker