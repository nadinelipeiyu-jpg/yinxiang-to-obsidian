#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
印象筆記本機資料庫 → Obsidian Markdown 轉換工具（進階版）

功能：
1. 直接讀取印象筆記 Mac App 的本機資料庫（SQLite + ENML 快取）
2. 完整複製圖片與附件
3. 自動處理過長檔名、URL encode 檔名、非法字元
4. 附件依類型分資料夾：images / pdfs / audio / video / files
5. 避免附件同名覆蓋（全域去重）
6. 支援 Obsidian 相對路徑連結
7. 產出附件索引 CSV，方便後續檢查
"""

import csv
import hashlib
import mimetypes
import os
import re
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote

import html2text


# ===== 設定區域 =====
DB_PATH = os.path.expanduser(
    "~/Library/Application Support/com.yinxiang.Mac"
    "/accounts/app.yinxiang.com/27122805/localNoteStore/LocalNoteStore.sqlite"
)
CONTENT_DIR = os.path.expanduser(
    "~/Library/Application Support/com.yinxiang.Mac"
    "/accounts/app.yinxiang.com/27122805/content"
)
OUTPUT_FOLDER = "/Volumes/EZ好好玩/ever印象筆"

# 測試模式：設成 10 只跑前 10 篇，確認沒問題後改成 0（代表全部）
TEST_LIMIT = 0

# 附件根目錄（Obsidian 可設定這個資料夾作為附件位置）
ATTACHMENTS_ROOT_NAME = "_attachments"

# 單一檔名保守上限，避免 macOS 255 bytes 問題
MAX_FILENAME_BYTES = 120
# ====================


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".tiff", ".bmp", ".heic"}
PDF_EXTS = {".pdf"}
AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}
VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm"}

MIME_EXT = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/svg+xml": ".svg",
    "image/tiff": ".tiff",
    "application/pdf": ".pdf",
    "audio/mpeg": ".mp3",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/mp4": ".m4a",
    "video/mp4": ".mp4",
    "video/quicktime": ".mov",
}


# ===== 基礎工具 =====
def clean_filename(name: str) -> str:
    """移除非法字元，讓檔名合法"""
    name = re.sub(r'[\\/*?:"<>|\n\r\t]', "_", str(name or ""))
    name = re.sub(r"\s+", " ", name).strip().strip(".")
    return name[:80] or "untitled"


def safe_unquote(text: str) -> str:
    """安全解碼 %E8%... 這類 URL encoded 字串，最多解 3 次"""
    text = str(text or "")
    prev = text
    for _ in range(3):
        decoded = unquote(prev)
        if decoded == prev:
            break
        prev = decoded
    return prev


def sanitize_filename(filename: str, max_bytes: int = MAX_FILENAME_BYTES) -> str:
    """處理過長 / 編碼 / 非法字元檔名，保留副檔名"""
    filename = safe_unquote(filename).strip()
    filename = filename.replace("/", "_").replace("\\", "_")
    filename = re.sub(r'[\x00-\x1f<>:"|?*]', "_", filename)
    filename = re.sub(r"\s+", " ", filename).strip().strip(".")

    if not filename:
        filename = "attachment.bin"

    p = Path(filename)
    stem = p.stem or "attachment"
    suffix = p.suffix

    if not suffix:
        guessed, _ = mimetypes.guess_type(filename)
        if guessed:
            suffix = MIME_EXT.get(guessed, "")

    suffix_bytes = suffix.encode("utf-8")
    allowed_stem_bytes = max_bytes - len(suffix_bytes)
    if allowed_stem_bytes < 16:
        allowed_stem_bytes = 16

    stem_bytes = stem.encode("utf-8")
    if len(stem_bytes) > allowed_stem_bytes:
        stem = stem_bytes[:allowed_stem_bytes].decode("utf-8", errors="ignore").rstrip(" .")
        if not stem:
            stem = "attachment"

    result = f"{stem}{suffix}".rstrip(" .")
    return result or "attachment.bin"


def hash_name(seed: str, suffix: str = "") -> str:
    digest = hashlib.md5(str(seed).encode("utf-8", errors="ignore")).hexdigest()[:12]
    if suffix and not suffix.startswith("."):
        suffix = "." + suffix
    return f"attachment_{digest}{suffix}"


def mac_timestamp_to_str(ts):
    """Apple Core Data 時間戳（從 2001-01-01 起算）→ 可讀字串"""
    if not ts:
        return ""
    try:
        apple_epoch = datetime(2001, 1, 1, tzinfo=timezone.utc)
        dt = datetime.fromtimestamp(apple_epoch.timestamp() + float(ts), tz=timezone.utc)
        return dt.astimezone().strftime("%Y-%m-%d %H:%M")
    except Exception:
        return str(ts)


def guess_ext(filename: str, mime: str, fallback: str = ".bin") -> str:
    if filename and Path(filename).suffix:
        return Path(filename).suffix.lower()
    if mime:
        return MIME_EXT.get(mime, fallback)
    return fallback


def pick_attachment_subfolder(ext: str) -> str:
    ext = ext.lower()
    if ext in IMAGE_EXTS:
        return "images"
    if ext in PDF_EXTS:
        return "pdfs"
    if ext in AUDIO_EXTS:
        return "audio"
    if ext in VIDEO_EXTS:
        return "video"
    return "files"


# ===== 附件索引與去重 =====
class AttachmentRegistry:
    def __init__(self, attachments_root: Path):
        self.attachments_root = attachments_root
        self.used_relpaths = set()
        self.rows = []

    def unique_relpath(self, subfolder: str, filename: str) -> Path:
        rel = Path(subfolder) / filename
        if rel.as_posix() not in self.used_relpaths and not (self.attachments_root / rel).exists():
            self.used_relpaths.add(rel.as_posix())
            return rel

        stem = Path(filename).stem
        suffix = Path(filename).suffix
        for i in range(1, 10000):
            alt = Path(subfolder) / f"{stem}_{i}{suffix}"
            if alt.as_posix() not in self.used_relpaths and not (self.attachments_root / alt).exists():
                self.used_relpaths.add(alt.as_posix())
                return alt

        fallback = Path(subfolder) / hash_name(filename, suffix)
        self.used_relpaths.add(fallback.as_posix())
        return fallback

    def add_row(self, note_title, note_uuid, hash_hex, src_path, rel_path, mime):
        self.rows.append({
            "note_title": note_title,
            "note_uuid": note_uuid,
            "hash_hex": hash_hex,
            "src_path": str(src_path),
            "rel_path": rel_path.as_posix(),
            "mime": mime or "",
        })

    def write_csv(self, output_folder: Path):
        if not self.rows:
            return
        csv_path = output_folder / "_attachment_index.csv"
        with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["note_title", "note_uuid", "hash_hex", "src_path", "rel_path", "mime"],
            )
            writer.writeheader()
            writer.writerows(self.rows)


# ===== DB / Resource =====
def build_resource_map(conn, note_pk):
    """
    從 ZENRESOURCE 建立 hash → 資源資訊 的對照表
    ENML 裡的 <en-media hash="abc123"> 就靠這個找到實際檔案
    """
    cur = conn.cursor()
    cur.execute(
        """
        SELECT r.ZDATAHASH, r.ZLOCALUUID, r.ZFILENAME, r.ZMIME,
               n.ZLOCALUUID as note_uuid
        FROM ZENRESOURCE r
        JOIN ZENNOTE n ON r.ZNOTE = n.Z_PK
        WHERE r.ZNOTE = ? AND r.ZDATAHASH IS NOT NULL
        """,
        (note_pk,),
    )

    resource_map = {}
    seen_names = {}

    for data_hash, res_uuid, filename, mime, note_uuid in cur.fetchall():
        hash_hex = data_hash.hex()
        ext = guess_ext(filename, mime)

        if filename:
            base = Path(safe_unquote(filename)).stem or res_uuid
        else:
            base = res_uuid

        base = clean_filename(base)
        output_name = f"{base}{ext}"

        if output_name in seen_names:
            seen_names[output_name] += 1
            output_name = f"{base}_{seen_names[output_name]}{ext}"
        else:
            seen_names[output_name] = 0

        src_path = Path(CONTENT_DIR) / note_uuid / f"{res_uuid}{ext}"
        if not src_path.exists():
            candidates = list((Path(CONTENT_DIR) / note_uuid).glob(f"{res_uuid}.*"))
            candidates = [c for c in candidates if c.suffix != ".en-reco"]
            if candidates:
                src_path = candidates[0]
            else:
                no_ext_path = Path(CONTENT_DIR) / note_uuid / res_uuid
                if no_ext_path.exists():
                    src_path = no_ext_path

        resource_map[hash_hex] = {
            "src_path": src_path,
            "output_name": output_name,
            "mime": mime,
            "note_uuid": note_uuid,
        }

    return resource_map


def safe_copy_attachment(resource_info, attachments_root: Path, registry: AttachmentRegistry, note_title: str, hash_hex: str):
    src_path = Path(resource_info["src_path"])
    output_name = resource_info["output_name"]
    mime = resource_info.get("mime")
    note_uuid = resource_info.get("note_uuid") or ""

    if not src_path.exists():
        return None

    ext = src_path.suffix.lower() or Path(output_name).suffix.lower() or guess_ext(output_name, mime)
    safe_name = sanitize_filename(output_name)
    if not Path(safe_name).suffix and ext:
        safe_name += ext

    if len(safe_name.encode("utf-8")) > MAX_FILENAME_BYTES:
        safe_name = hash_name(output_name, ext)

    subfolder = pick_attachment_subfolder(ext)
    rel_path = registry.unique_relpath(subfolder, safe_name)
    dest_path = attachments_root / rel_path
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        shutil.copy2(str(src_path), str(dest_path))
    except OSError:
        fallback_name = hash_name(output_name, ext)
        rel_path = registry.unique_relpath(subfolder, fallback_name)
        dest_path = attachments_root / rel_path
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(src_path), str(dest_path))

    registry.add_row(note_title, note_uuid, hash_hex, src_path, rel_path, mime)
    return rel_path


# ===== ENML → Markdown =====
def replace_media_tags(enml_text, resource_map, attachments_root, registry, note_title):
    """
    把 ENML 裡的 <en-media hash="..."> 替換成 Obsidian 的 ![[...]] / [[...]]
    同時把對應的附件複製到 attachments_root
    """

    def replace_one(match):
        hash_val = re.search(r'hash=["\']([a-f0-9]+)["\']', match.group(0))
        if not hash_val:
            return ""
        hash_hex = hash_val.group(1)

        if hash_hex not in resource_map:
            return f"<!-- 附件未找到: {hash_hex[:8]}... -->"

        resource_info = resource_map[hash_hex]
        rel_path = safe_copy_attachment(resource_info, attachments_root, registry, note_title, hash_hex)
        if rel_path is None:
            return f"<!-- 附件檔案不存在: {hash_hex[:8]}... -->"

        rel_posix = rel_path.as_posix()
        ext = Path(rel_posix).suffix.lower()
        if ext in IMAGE_EXTS:
            return f"![[{rel_posix}]]"
        return f"[[{rel_posix}]]"

    result = re.sub(r"<en-media[^>]*/>", replace_one, enml_text)
    result = re.sub(r"<en-media[^>]*></en-media>", replace_one, result)
    return result


def enml_to_markdown(enml_text, resource_map, attachments_root, registry, note_title):
    enml_text = replace_media_tags(enml_text, resource_map, attachments_root, registry, note_title)

    converter = html2text.HTML2Text()
    converter.ignore_links = False
    converter.ignore_images = False
    converter.body_width = 0
    converter.unicode_snob = True
    try:
        md = converter.handle(enml_text)
        md = re.sub(r"\n{3,}", "\n\n", md)
        return md.strip()
    except Exception as e:
        return f"（內容轉換失敗：{e}）"


# ===== Note / Tags =====
def get_note_tags(conn, note_pk):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT t.ZNAME FROM ZENTAG t
        JOIN Z_10TAGS jt ON t.Z_PK = jt.Z_23TAGS
        WHERE jt.Z_10NOTES = ?
        """,
        (note_pk,),
    )
    return [row[0] for row in cur.fetchall() if row[0]]


def note_to_markdown_file(note, tags, content_md):
    tag_str = ""
    if tags:
        tag_list = "\n".join([f'  - "{str(t).replace(chr(34), chr(39))}"' for t in tags])
        tag_str = f"\ntags:\n{tag_list}"

    frontmatter = f"""---
title: \"{note['title'].replace(chr(34), chr(39))}\"
created: {note['created']}
updated: {note['updated']}{tag_str}
source: 印象筆記
---

# {note['title']}

"""
    return frontmatter + (content_md or "（此筆記內容未同步到本機）")


# ===== Main =====
def main():
    db_path = Path(DB_PATH)
    output_folder = Path(OUTPUT_FOLDER)
    attachments_root = output_folder / ATTACHMENTS_ROOT_NAME

    if not db_path.exists():
        print(f"❌ 找不到印象筆記資料庫：{DB_PATH}")
        return

    output_folder.mkdir(parents=True, exist_ok=True)
    attachments_root.mkdir(parents=True, exist_ok=True)
    for sub in ["images", "pdfs", "audio", "video", "files"]:
        (attachments_root / sub).mkdir(parents=True, exist_ok=True)

    registry = AttachmentRegistry(attachments_root)

    print("\n📂 讀取印象筆記本機資料庫...")
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()

    cur.execute(
        """
        SELECT
            n.Z_PK,
            n.ZTITLE,
            n.ZLOCALUUID,
            n.ZDATECREATED,
            n.ZDATEUPDATED,
            nb.ZNAME as notebook_name
        FROM ZENNOTE n
        LEFT JOIN ZENNOTEBOOK nb ON n.ZNOTEBOOK = nb.Z_PK
        WHERE n.ZACTIVE = 1
        ORDER BY nb.ZNAME, n.ZDATEUPDATED DESC
        """
    )
    notes = cur.fetchall()
    total_all = len(notes)

    if TEST_LIMIT > 0:
        notes = notes[:TEST_LIMIT]
        print(f"🧪 測試模式：只處理前 {TEST_LIMIT} 篇（共 {total_all} 篇）\n")
    else:
        print(f"✅ 找到 {total_all} 條筆記（不含垃圾桶）\n")

    success = 0
    no_content = 0
    total_attachments = 0

    for i, row in enumerate(notes, 1):
        pk, title, note_uuid, created_ts, updated_ts, notebook_name = row
        title = title or "untitled"
        notebook_name = notebook_name or "未分類"

        print(f"[{i}/{len(notes)}] {title[:40]}")

        tags = get_note_tags(conn, pk)
        resource_map = build_resource_map(conn, pk)
        total_attachments += len(resource_map)

        content_path = Path(CONTENT_DIR) / note_uuid / "content.enml"
        if content_path.exists():
            enml = content_path.read_text(encoding="utf-8")
            content_md = enml_to_markdown(enml, resource_map, attachments_root, registry, title)
            success += 1
        else:
            content_md = None
            no_content += 1

        note_data = {
            "title": title,
            "created": mac_timestamp_to_str(created_ts),
            "updated": mac_timestamp_to_str(updated_ts),
        }
        md_text = note_to_markdown_file(note_data, tags, content_md)

        nb_folder = output_folder / clean_filename(notebook_name)
        nb_folder.mkdir(parents=True, exist_ok=True)

        filename = clean_filename(title) + ".md"
        output_path = nb_folder / filename
        counter = 1
        while output_path.exists():
            filename = clean_filename(title) + f"_{counter}.md"
            output_path = nb_folder / filename
            counter += 1

        output_path.write_text(md_text, encoding="utf-8")

    conn.close()
    registry.write_csv(output_folder)

    print("\n" + "=" * 50)
    if TEST_LIMIT > 0:
        print("🧪 測試完成！確認結果沒問題後，把 TEST_LIMIT 改成 0 再跑全部")
    else:
        print("✅ 完成！")
    print(f"   📝 轉換筆記：{success} 條")
    if no_content > 0:
        print(f"   ⚠️  無內容：{no_content} 條")
    print(f"   🖼️  附件總數：{total_attachments} 個")
    print(f"   📁 輸出位置：{output_folder}")
    print(f"   📎 附件位置：{attachments_root}")
    print(f"   🧾 索引檔：{output_folder / '_attachment_index.csv'}")
    print("\n💡 Obsidian 設定：Settings → Files & Links → Attachment folder → _attachments")
    print("=" * 50)


if __name__ == "__main__":
    main()
