# evernote-to-obsidian

將中國版本的印象筆記（Yinxiang）本機資料庫 → Obsidian Markdown 轉換工具

## 功能

- 直接讀取印象筆記 Mac App 的本機 SQLite 資料庫
- 完整複製圖片與附件，依類型分資料夾（images / pdfs / audio / video / files）
- 自動處理過長檔名、URL encode 檔名、非法字元
- 避免附件同名覆蓋（全域去重）
- 支援 Obsidian 相對路徑連結（`![[...]]`）
- 產出附件索引 CSV
- 保留筆記本階層、標籤、建立/更新時間

## 需求

- macOS
- 印象筆記 Mac App（需已登入並同步）
- Python 3.8+

## 安裝

```bash
pip3 install html2text
```

## 設定

打開 `evernote_to_obsidian.py`，修改第 31-49 行的設定區域：

```python
DB_PATH = os.path.expanduser(
    "~/Library/Application Support/com.yinxiang.Mac"
    "/accounts/app.yinxiang.com/[YOUR_USER_ID]/localNoteStore/LocalNoteStore.sqlite"
)
CONTENT_DIR = os.path.expanduser(
    "~/Library/Application Support/com.yinxiang.Mac"
    "/accounts/app.yinxiang.com/[YOUR_USER_ID]/content"
)
OUTPUT_FOLDER = "/path/to/your/obsidian/vault"
TEST_LIMIT = 10  # 先用 10 筆測試，確認沒問題改成 0 跑全部
```

### 找到 YOUR_USER_ID

```bash
ls ~/Library/Application\ Support/com.yinxiang.Mac/accounts/app.yinxiang.com/
```

## 執行

```bash
python3 evernote_to_obsidian.py
```

## Obsidian 設定

轉換完成後，在 Obsidian 設定：

Settings → Files & Links → Attachment folder path → `_attachments`

## 輸出結構

```
OUTPUT_FOLDER/
├── 筆記本名稱/
│   ├── 筆記標題.md
│   └── ...
├── _attachments/
│   ├── images/
│   ├── pdfs/
│   ├── audio/
│   ├── video/
│   └── files/
└── _attachment_index.csv
```

## Claude Code Skill 使用方式

1. 複製 `skill.md` 到 `~/.claude/commands/evernote-to-obsidian.md`
2. 在 Claude Code 中執行 `/evernote-to-obsidian`
3. Claude 會引導你完成設定與執行

## 常見問題

**Q: 找不到資料庫**  
A: 確認印象筆記 Mac App 已安裝、登入並完成同步

**Q: 筆記顯示「無內容」**  
A: 該筆記未下載到本機，在 App 中打開筆記讓它同步

**Q: 附件找不到**  
A: 同上，需在 App 中打開筆記讓附件下載

## 授權

MIT
