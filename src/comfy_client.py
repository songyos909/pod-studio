"""คุยกับ ComfyUI ผ่าน HTTP/WebSocket API.

ลำดับการทำงาน:
  1) POST /prompt          -> ส่ง workflow เข้าคิว ได้ prompt_id
  2) ws://.../ws           -> ฟังจนกว่าจะ generate เสร็จ
  3) GET /history/{id}     -> ดูว่ามีไฟล์ภาพอะไรบ้าง
  4) GET /view             -> ดึง bytes ของภาพ
"""

import json
import time
import urllib.parse
import uuid

import requests

try:
    import websocket  # มาจากแพ็กเกจ websocket-client
except ImportError as e:  # pragma: no cover
    raise ImportError(
        "ต้องติดตั้ง websocket-client ก่อน: pip install -r requirements.txt"
    ) from e


class ComfyUIError(Exception):
    """ข้อผิดพลาดทั่วไปจากการคุยกับ ComfyUI."""


class ComfyClient:
    def __init__(self, host="127.0.0.1", port=8188, client_id=None, timeout_sec=600):
        self.base = f"http://{host}:{port}"
        self.ws_base = f"ws://{host}:{port}"
        self.client_id = client_id or str(uuid.uuid4())
        self.timeout_sec = timeout_sec

    # ---------- helper: requests + retry ----------
    def _request(self, method, path, retries=3, **kwargs):
        url = f"{self.base}{path}"
        kwargs.setdefault("timeout", 60)
        last = None
        for attempt in range(retries):
            try:
                r = requests.request(method, url, **kwargs)
                if r.status_code >= 400:
                    raise ComfyUIError(f"{method} {path} -> {r.status_code}: {r.text}")
                return r
            except (requests.RequestException, ComfyUIError) as e:
                last = e
                # 4xx จาก ComfyUI (เช่น workflow ไม่ถูกต้อง) ลองซ้ำก็ไม่หาย
                if isinstance(e, ComfyUIError):
                    raise
                time.sleep(1.5 * (attempt + 1))
        raise ComfyUIError(f"{method} {path} ล้มเหลวหลังลอง {retries} ครั้ง: {last}")

    # ---------- public API ----------
    def ping(self):
        """เช็กว่า ComfyUI เปิดอยู่ไหม."""
        try:
            r = requests.get(f"{self.base}/system_stats", timeout=10)
            return r.status_code == 200
        except requests.RequestException:
            return False

    def object_info(self, node_class):
        """ดึง metadata ของ node หนึ่ง (เช่นรายชื่อ checkpoint/sampler ที่มี)."""
        r = self._request("GET", f"/object_info/{node_class}", retries=1, timeout=15)
        return r.json()

    def list_checkpoints(self):
        """รายชื่อไฟล์โมเดล (.safetensors) ที่ ComfyUI เห็น."""
        try:
            info = self.object_info("CheckpointLoaderSimple")
            opts = info["CheckpointLoaderSimple"]["input"]["required"]["ckpt_name"][0]
            return list(opts)
        except Exception:
            return []

    def list_samplers(self):
        """คืน (samplers, schedulers) จาก KSampler."""
        try:
            info = self.object_info("KSampler")
            req = info["KSampler"]["input"]["required"]
            return list(req["sampler_name"][0]), list(req["scheduler"][0])
        except Exception:
            return [], []

    def queue_prompt(self, workflow):
        payload = {"prompt": workflow, "client_id": self.client_id}
        r = self._request("POST", "/prompt", json=payload, timeout=30)
        data = r.json()
        if "prompt_id" not in data:
            raise ComfyUIError(f"ComfyUI ไม่คืน prompt_id: {data}")
        return data["prompt_id"]

    def wait_until_done(self, prompt_id):
        """ฟัง websocket จนกว่า node สุดท้ายของ prompt_id นี้จะทำงานเสร็จ."""
        ws = websocket.WebSocket()
        try:
            ws.connect(f"{self.ws_base}/ws?clientId={self.client_id}", timeout=30)
            ws.settimeout(self.timeout_sec)
            deadline = time.time() + self.timeout_sec
            while True:
                if time.time() > deadline:
                    raise ComfyUIError("หมดเวลารอ ComfyUI generate")
                try:
                    msg = ws.recv()
                except websocket.WebSocketTimeoutException as e:
                    raise ComfyUIError("หมดเวลารอ ComfyUI generate") from e
                if isinstance(msg, (bytes, bytearray)):
                    continue  # binary = ภาพ preview ระหว่างทาง ข้ามไป
                data = json.loads(msg)
                if data.get("type") == "executing":
                    d = data.get("data", {})
                    if d.get("node") is None and d.get("prompt_id") == prompt_id:
                        return  # เสร็จแล้ว
        finally:
            try:
                ws.close()
            except Exception:
                pass

    def get_history(self, prompt_id):
        r = self._request("GET", f"/history/{prompt_id}", timeout=30)
        return r.json()

    def get_image_bytes(self, filename, subfolder, folder_type):
        params = urllib.parse.urlencode(
            {"filename": filename, "subfolder": subfolder, "type": folder_type}
        )
        r = self._request("GET", f"/view?{params}", timeout=120)
        return r.content

    def generate(self, workflow):
        """ส่ง workflow แล้วคืน list ของ dict {filename, data(bytes)}."""
        prompt_id = self.queue_prompt(workflow)
        self.wait_until_done(prompt_id)
        history = self.get_history(prompt_id)
        if prompt_id not in history:
            raise ComfyUIError("ไม่พบผลลัพธ์ใน /history")

        images = []
        outputs = history[prompt_id].get("outputs", {})
        for _node_id, node_output in outputs.items():
            for img in node_output.get("images", []):
                data = self.get_image_bytes(
                    img["filename"], img.get("subfolder", ""), img.get("type", "output")
                )
                images.append({"filename": img["filename"], "data": data})
        return images
