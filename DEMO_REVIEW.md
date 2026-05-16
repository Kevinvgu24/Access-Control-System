# Demo Review - Access Control System

## Tong quan

Repo nay la mot demo he thong kiem soat truy cap bang nhan dien khuon mat, chay theo pipeline:

1. Doc camera realtime.
2. Dung YOLO tren Hailo NPU de phat hien khuon mat.
3. Can chinh mat bang OpenCV LBF landmark model.
4. Dung ArcFace tren Hailo NPU de trich xuat embedding.
5. So sanh embedding voi SQLite database bang cosine similarity.
6. Hien thi bounding box, ten nguoi dung, do tin cay, FPS va nhiet do phan cung.

Phien ban chinh cua chuong trinh nam trong `src/Newest_Version`.

## Diem manh

- Cau truc module kha ro rang: `app.py`, `camera.py`, `face_engine.py`, `database.py`, `auto_sync_service.py`, `common.py`.
- Co su dung `npu_lock` de tranh tranh chap tai nguyen Hailo NPU giua camera thread va sync thread.
- Co auto-sync database khi them hoac xoa thu muc nguoi dung trong `database/`.
- Co face alignment truoc khi dua vao ArcFace, giup cai thien do chinh xac nhan dien.
- Co face tracker de lam muot embedding qua nhieu frame.
- Co hien thi FPS va nhiet do CPU/Hailo, phu hop cho demo edge AI.

## Van de can chu y

### 1. Logic hien thi danh tinh co the gay hieu nham

Trong `app.py`, chuong trinh luon hien thi ten nguoi co similarity cao nhat, ngay ca khi diem thap hon threshold. Khi similarity khong dat nguong, UI nen hien thi `Unknown` thay vi ten nguoi gan nhat.

### 2. Chua co anti-spoofing hoac liveness detection

He thong hien tai co the bi danh lua bang anh hoac video khuon mat. Voi demo thi chap nhan duoc, nhung neu dung cho cua that can bo sung liveness detection.

### 3. Auto-sync chua cap nhat nguoi dung cu khi them anh moi

`auto_sync_service.py` hien chi xu ly user moi va user bi xoa. Neu them anh moi vao folder cua user da ton tai, embedding se khong duoc tinh lai.

### 4. YOLO postprocess chua co NMS ro rang

`common.py` decode bounding box tu cac output tensor, nhung chua thay buoc Non-Maximum Suppression. Dieu nay co the tao nhieu box trung nhau tren cung mot khuon mat.

### 5. Hieu nang inference co the chua toi uu

Moi lan infer, `common.py` kich hoat network group va tao `InferVStreams`. Neu Hailo API cho phep, nen giu pipeline inference song lau hon de giam overhead realtime.

### 6. Thread shutdown chua sach

`AutoSyncManager` co bien `running`, nhung `app.py` chua goi stop cho sync manager trong khoi `finally`.

### 7. Config con hard-code

Mot so tham so nhu recognition threshold, YOLO confidence, camera size, camera device va sync interval dang nam truc tiep trong code. Nen tach thanh file config hoac CLI args.

### 8. Database sinh trac hoc con don gian

Moi user chi luu mot embedding trung binh. Cach nay nhanh, nhung nen can nhac luu nhieu embedding cho moi user de ho tro nhieu goc mat va dieu kien anh sang.

### 9. Xu ly loi con theo kieu demo

Mot so loi trong `face_engine.py` goi `sys.exit(1)` truc tiep. Nen chuyen sang raise exception de tang kha nang test va kiem soat loi o tang app.

### 10. Repo can don dep truoc khi chia se

Repo hien co `__pycache__`, log Hailo, SQLite database, anh nguoi dung va model lon. Nen dung `.gitignore`, Git LFS hoac tach data/model khoi source code.

## Cai thien uu tien

1. Sua logic `Unknown` trong `app.py`.
2. Them NMS cho YOLO postprocess trong `common.py`.
3. Cai thien auto-sync de phat hien anh moi/sua/xoa trong folder user cu.
4. Tach config ra file rieng hoac command-line arguments.
5. Thay `print` bang logging chuan co timestamp va log level.
6. Them access log cho cac su kien accepted/rejected.
7. Them liveness detection neu dung cho he thong cua that.
8. Them test cho `utils.py`, `database.py`, bbox scaling va identity decision logic.
9. Sua encoding tieng Viet trong comment va tai lieu.
10. Chuan hoa `requirements.txt` va them README huong dan chay.

## Ket luan

Demo nay da co pipeline edge AI kha day du va phu hop de trinh dien. De tien gan hon mot he thong access-control san sang van hanh, can uu tien do tin cay nhan dien, bao mat sinh trac hoc, kha nang dong bo database, logging va quan ly cau hinh.

## Thay doi da thuc hien

- Sua logic hien thi danh tinh: neu similarity khong vuot `rec_thresh`, UI hien `Unknown` thay vi ten nguoi gan nhat.
- Them Non-Maximum Suppression cho YOLO postprocess de giam box trung lap.
- Cai thien auto-sync: he thong phat hien thay doi anh trong folder user cu, khong chi xu ly user moi.
- Luu chu ky anh vao SQLite bang `user_sync_state` de auto-sync co the nhan biet thay doi qua cac lan chay.
- Them `stop()` cho `AutoSyncManager` va goi khi app thoat de shutdown thread sach hon.
