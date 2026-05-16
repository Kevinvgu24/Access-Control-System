import sqlite3
import numpy as np
import io

# 1. Thủ thuật chuyển Numpy Array thành Nhị phân để lưu vào SQLite
def adapt_array(arr):
    out = io.BytesIO()
    np.save(out, arr)
    out.seek(0)
    return sqlite3.Binary(out.read())

def convert_array(text):
    out = io.BytesIO(text)
    out.seek(0)
    return np.load(out)

sqlite3.register_adapter(np.ndarray, adapt_array)
sqlite3.register_converter("array", convert_array)

# 2. Các hàm tương tác với Database
class FaceDatabase:
    def __init__(self, db_path="smart_door.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        # Tạo bảng nếu chưa tồn tại
        conn = sqlite3.connect(self.db_path, detect_types=sqlite3.PARSE_DECLTYPES)
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                embedding array
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS user_sync_state (
                name TEXT PRIMARY KEY,
                image_signature TEXT NOT NULL
            )
        ''')
        conn.commit()
        conn.close()

    def save_user(self, name, embedding):
        conn = sqlite3.connect(self.db_path, detect_types=sqlite3.PARSE_DECLTYPES)
        c = conn.cursor()
        try:
            c.execute("REPLACE INTO users (name, embedding) VALUES (?, ?)", (name, embedding))
            conn.commit()
            print(f"[DATABASE] Đã lưu/cập nhật hồ sơ: {name}")
        except Exception as e:
            print(f"[DATABASE] Lỗi khi lưu {name}: {e}")
        finally:
            conn.close()

    # --- THÊM HÀM MỚI NÀY VÀO ---
    def delete_user(self, name):
        conn = sqlite3.connect(self.db_path, detect_types=sqlite3.PARSE_DECLTYPES)
        c = conn.cursor()
        try:
            c.execute("DELETE FROM users WHERE name = ?", (name,))
            c.execute("DELETE FROM user_sync_state WHERE name = ?", (name,))
            conn.commit()
            print(f"[DATABASE] Đã xóa vĩnh viễn hồ sơ: {name}")
        except Exception as e:
            print(f"[DATABASE] Lỗi khi xóa {name}: {e}")
        finally:
            conn.close()

    def save_sync_signature(self, name, image_signature):
        conn = sqlite3.connect(self.db_path, detect_types=sqlite3.PARSE_DECLTYPES)
        c = conn.cursor()
        try:
            c.execute(
                "REPLACE INTO user_sync_state (name, image_signature) VALUES (?, ?)",
                (name, image_signature),
            )
            conn.commit()
        except Exception as e:
            print(f"[DATABASE] Loi khi luu sync state {name}: {e}")
        finally:
            conn.close()

    def load_sync_signatures(self):
        conn = sqlite3.connect(self.db_path, detect_types=sqlite3.PARSE_DECLTYPES)
        c = conn.cursor()
        c.execute("SELECT name, image_signature FROM user_sync_state")
        rows = c.fetchall()
        conn.close()
        return {row[0]: row[1] for row in rows}

    def load_all_users(self):
        conn = sqlite3.connect(self.db_path, detect_types=sqlite3.PARSE_DECLTYPES)
        c = conn.cursor()
        c.execute("SELECT name, embedding FROM users")
        rows = c.fetchall()
        conn.close()
        
        # Trả về một Dictionary dạng: {"Kien": [Vector...], "Tuan": [Vector...]}
        return {row[0]: row[1] for row in rows}
