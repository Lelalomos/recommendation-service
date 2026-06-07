how does it work:
1. ข้อมูลของ user จะเข้ามาทาง API 
2. API ส่งข้อมูลที่เป็น queue message ไปที่ rabbitmq 
3. rabbitMQ ส่งข้อมูลเข้า worker
4. worker เช็คข้อมูล user จาก postgresql และดึงข้อมูลออกมา
5. ส่งข้อมูลที่ดึงมาได้เข้าไปคำนวณ similarity(คำนวณความเหมือนของตัวอักษร) ใน vector database
6. sort ข้อมูลที่ได้จาก vector database และส่งผลกลับไปที่ API

how to feed input and get output
การส่งข้อมูลทำได้ 2 รูปแบบดังนี้
1. ใช้ Postman ในการช่วยยิง request เข้าไปใน API (ไฟล์ Postman อยู่ใน Postman folder)
2. ใช้ Swagger UI ของ FastAPI ในการยิงข้อมูลเข้า API

how to improve in the feaure
1. การคำนวณคะแนนความเหมือน(similarity) ต้องใช้ข้อมูลของ user คนนั้นทั้งหมด (ตอนนี้ยังใช้แค่ข้อมูลที่ส่งมาจาก API เท่านั้น)
2. เปลี่ยนรูปแบบของการรับข้อมูลเป็นการใช้ Callback API เนื่องจากมีโอกาสที่ตัวคำนวณหรือตัว model จะใช้เวลานานแล้วทำให้ API ที่รอ timeout ได้
3. ดึง config ทั้งหมดเข้าไปใน Database เพื่อที่เวลาจะเปลี่ยน config จะได้ไม่ต้องทำการ restart service ทุกรอบ ยกตัวอย่างเช่นการ set ค่า weight ในการคำนวณ ค่าความเหมือน(similarity) จะสามารถเปลี่ยนได้ทุกเมื่อเพียงแค่เปลี่ยน config จาก database และ service ที่คำนวณต้องเพิ่ม process การดึงข้อมูล config ใน Database ทุกครั้งก่อนเริ่มทำงาน

how to setup recommended system

รันทุก service ขึ้นมาโดยการใช้คำสั่งดังนี้
1. ให้ terminal เข้ามาที่ recommendation-service folder
2. เข้าไปใน api-service folder แล้วรัน ./scripts/start_api_compose.sh ใช้คำสั่งนี้เพื่อ build และ run service ของ API
3. เข้าไปใน postgresql folder แล้วรัน ./scripts/start_postgres_compose.sh ใช้คำสั่งนี้เพื่อ build และ run service ของ PostgreSQL database
4. เข้าไปใน rabbitmq folder แล้วรัน ./scripts/start_rabbitmq_compose.sh ใช้คำสั่งนี้เพื่อ build และ run service ของ RabbitMQ
5. เข้าไปใน vector_db folder แล้วรัน ./scripts/start_qdrant_compose.sh ใช้คำสั่งนี้เพื่อ build และ run service ของ Vector Database
6. เข้าไปใน worker folder แล้วรัน ./scripts/start_worker_compose.sh ใช้คำสั่งนี้เพื่อ build และ run service ของ worker
