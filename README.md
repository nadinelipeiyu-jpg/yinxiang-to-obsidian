# yinxiang-to-obsidian

印象筆記（Yinxiang）本機資料庫 → Obsidian Markdown 轉換工具

## 為什麼做這個工具？

印象筆記（Yinxiang）的 Mac App 導出格式是 `.note` 檔，**不是**標準的 Evernote `.enex` 格式。

這代表你無法直接用 Obsidian 的 Importer 插件導入，而印象筆記本身的導出流程也非常繁瑣。

這個工具直接讀取印象筆記 Mac App 的**本機 SQLite 資料庫**，繞過導出步驟，一鍵轉成 Obsidian 可用的 Markdown 格式。

## 功能

- 直接讀取印象筆記 Mac App 本機 SQLite 資料庫，不需要導出
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

## 前置確認：找到印象筆記的本機資料庫位置

在設定腳本之前，請先確認印象筆記的資料確實存在於本機。

### 方法一：使用磁碟工具（推薦）

1. 開啟 **Finder** → 前往 → 前往檔案夾（或按 `Cmd + Shift + G`）
2. 輸入以下路徑：
   ```
   ~/Library/Application Support/com.yinxiang.Mac
   ```
3. 確認資料夾存在，且裡面有 `accounts/` 目錄
4. 進入 `accounts/app.yinxiang.com/`，你會看到一個數字 ID 的資料夾（這就是你的 USER_ID）
5. 確認該資料夾內有 `localNoteStore/LocalNoteStore.sqlite` 這個檔案

> 如果找不到這個路徑，代表印象筆記尚未在本機建立資料庫。請先打開印象筆記 App，登入後等待同步完成。

### 方法二：用 Terminal 確認

```bash
ls ~/Library/Application\ Support/com.yinxiang.Mac/accounts/app.yinxiang.com/
```

有看到數字 ID 資料夾，就代表資料庫存在，可以繼續設定。

---

## 設定

打開 `yinxiang_to_obsidian.py`，修改第 31-49 行的設定區域：

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
python3 yinxiang_to_obsidian.py
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

**Q: 執行到一半卡住、出現檔名相關錯誤**  
A: 通常是附件檔名過長（超過系統限制）或含有特殊字元導致。腳本已內建處理邏輯，若仍發生請確認 Python 版本為 3.8+，並回報錯誤訊息

**Q: 部分附件轉移後找不到**  
A: 可能原因有兩個：
1. 附件尚未下載到本機 → 在印象筆記 App 中打開該筆記讓附件同步
2. 附件檔名與其他檔案衝突 → 查看輸出的 `_attachment_index.csv` 確認對應關係

## 授權

MIT
