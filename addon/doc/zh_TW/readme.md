# Invisinote

Invisinote 是一個 NVDA 附加元件，讓您不必離開目前正在使用的程式就能閱讀純文字筆記。
它不會開啟任何視窗，焦點也不會移動：筆記會載入記憶體中，完全以鍵盤手勢瀏覽，
您所在的程式仍保有焦點。

## 開始使用

1. 開啟 NVDA 設定對話框，並選擇 **Invisinote** 類別。
2. 新增一個或多個存放筆記的資料夾，以及要讀取的副檔名（預設為 `txt`）。
3. 按下 NVDA+ALT+N 載入目前資料夾中的筆記，NVDA 會報出找到幾則筆記。
4. 以 NVDA+ALT+U 和 NVDA+ALT+O 在筆記之間移動，再用下列手勢逐行、逐字詞
   或逐字元閱讀。

筆記會依檔名排序讀取。再次載入（NVDA+ALT+N）即可取得之後新增或修改的檔案。

## 手勢

### 資料夾與筆記

* NVDA+ALT+P：在檔案總管中開啟目前資料夾
* NVDA+ALT+\[：上一個資料夾
* NVDA+ALT+]：下一個資料夾
* NVDA+ALT+N：載入目前資料夾中的筆記
* NVDA+ALT+U：上一則筆記
* NVDA+ALT+O：下一則筆記

### 閱讀

* NVDA+ALT+SHIFT+A：朗讀整則筆記
* NVDA+ALT+I：上一行
* NVDA+ALT+K：下一行
* NVDA+ALT+J：上一個字詞
* NVDA+ALT+L：下一個字詞
* NVDA+ALT+,：上一個字元
* NVDA+ALT+.：下一個字元
* NVDA+ALT+H：行首
* NVDA+ALT+'：行尾
* NVDA+ALT+Space：將筆記轉譯為 Markdown，並在瀏覽模式視窗中閱讀

### 複製

* NVDA+ALT+A：複製整則筆記
* NVDA+ALT+;：複製目前這一行
* NVDA+ALT+F9：在目前位置設定選取起點
* NVDA+ALT+F10：設定選取終點；連按兩次即複製選取內容
* NVDA+ALT+BACKSPACE：清除選取標記

### 編碼

* NVDA+ALT+E：切換至下一個筆記編碼
* NVDA+ALT+SHIFT+E：切換至上一個筆記編碼

移至其他筆記會重設行、字詞與字元位置；在行之間移動會重設字詞與字元位置；
任何非選取的移動指令都會清除選取標記。

## 設定

設定位於 NVDA 設定對話框中的 **Invisinote** 類別。
NVDA 的「輸入手勢」對話框中，invisinote 類別下有「開啟 Invisinote 設定」指令，
可直接跳至該類別；若您想要專屬快速鍵，可在此自行指派。

* **資料夾** — Invisinote 讀取筆記的資料夾。可用 NVDA+ALT+\[ 和 NVDA+ALT+]
  在這些資料夾之間移動。
* **檔案類型** — 視為筆記的副檔名，例如 `txt` 或 `md`。
* **循環編碼** — NVDA+ALT+E 和 NVDA+ALT+SHIFT+E 會依序切換的編碼。
  取消勾選您用不到的編碼，可讓循環更精簡。若目前使用的編碼被取消勾選，
  Invisinote 會改用仍啟用的第一個編碼。

可用的編碼有 UTF-8、UTF-8 with BOM、Big5（繁體中文）、GB18030（簡體中文）、
Windows-1252 與 Latin-1。若筆記無法以目前編碼解碼，會改以 Latin-1 重新讀取，
確保閱讀不會直接失敗。

## 專案資訊

Invisinote 是開放原始碼的 NVDA 附加元件，採用 GNU GPL v2 授權。

* 儲存庫：<https://github.com/ClippyCat/invisinote>
* 作者：ClippyCat
* 問題回報與功能建議：<https://github.com/ClippyCat/invisinote/issues>

本附加元件以 SCons 建置；建置與開發說明請見儲存庫中的 `CLAUDE.md`。
歡迎貢獻與翻譯 — 新語言請放在 `addon/locale/<lang>/LC_MESSAGES/nvda.po`。
