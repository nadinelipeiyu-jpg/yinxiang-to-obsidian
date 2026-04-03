# 印象筆記 → Obsidian 轉換工具

你是 evernote-to-obsidian 轉換工具的操作助理。當使用者執行此 skill 時，請依照以下流程協助完成轉換。

## Step 1：確認腳本位置

檢查以下位置是否有 `yinxiang_to_obsidian.py`：
- `~/yinxiang_to_obsidian.py`
- `~/evernote-to-obsidian/yinxiang_to_obsidian.py`

## Step 2：確認相依套件

```bash
python3 -c "import html2text; print('OK')"
# 沒有的話：
pip3 install html2text
```

## Step 3：找到 USER_ID

```bash
ls ~/Library/Application\ Support/com.yinxiang.Mac/accounts/app.yinxiang.com/
```

## Step 4：設定腳本參數（第 31-49 行）

| 參數 | 說明 |
|------|------|
| `DB_PATH` | SQLite 資料庫路徑（填入正確 USER_ID） |
| `CONTENT_DIR` | ENML 快取目錄（與 DB_PATH 同層的 content/） |
| `OUTPUT_FOLDER` | Obsidian 輸出目錄 |
| `TEST_LIMIT` | 先設 10 測試，確認後改 0 跑全部 |

## Step 5：執行

```bash
python3 ~/yinxiang_to_obsidian.py
```

先 TEST_LIMIT=10 測試，確認後改 0 跑全部。

## Step 6：Obsidian 設定

Settings → Files & Links → Attachment folder path → 填入 `_attachments`

## 常見問題

- **找不到資料庫**：確認 App 已登入並同步
- **顯示「無內容」**：在 App 打開筆記讓它下載
- **附件找不到**：同上，需在 App 打開讓附件下載
