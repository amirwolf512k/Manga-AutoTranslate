@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

echo ========================================
echo  مترجم خودکار مانگا / مانهوا (فارسی)
echo ========================================
echo.
where python >nul 2>&1
if errorlevel 1 (
    echo خطا: Python پیدا نشد. لطفاً اول نصبش کنید.
    pause
    exit /b 1
)

echo ۱) ارائه‌دهنده AI را انتخاب کنید:
echo  1) gemini      (Google Gemini - رایگان با سهمیه)
echo  2) openai      (ChatGPT / GPT)
echo  3) deepseek    (DeepSeek)
echo  4) groq        (Groq - سریع و رایگان)
echo  5) xai         (xAI / Grok)
echo  6) openrouter  (OpenRouter)
echo  7) ollama      (لوکال - بدون کلید)
echo  8) together    (Together AI)
set /p "prov_choice=انتخاب [پیش‌فرض 1]: "
if "!prov_choice!"=="" set prov_choice=1

if "!prov_choice!"=="1" set PROVIDER=gemini
if "!prov_choice!"=="2" set PROVIDER=openai
if "!prov_choice!"=="3" set PROVIDER=deepseek
if "!prov_choice!"=="4" set PROVIDER=groq
if "!prov_choice!"=="5" set PROVIDER=xai
if "!prov_choice!"=="6" set PROVIDER=openrouter
if "!prov_choice!"=="7" set PROVIDER=ollama
if "!prov_choice!"=="8" set PROVIDER=together
if not defined PROVIDER set PROVIDER=gemini
echo ارائه‌دهنده: !PROVIDER!
echo.

REM نصب پکیج مربوط به provider
if "!PROVIDER!"=="gemini" (
    python -c "import google.genai" 2>nul
    if errorlevel 1 (
        echo نصب google-genai...
        pip install --no-cache-dir google-genai
    )
) else (
    python -c "import openai" 2>nul
    if errorlevel 1 (
        echo نصب openai...
        pip install --no-cache-dir openai
    )
)

set "API_KEYS="
set "MODEL_NAME="
if not "!PROVIDER!"=="ollama" (
    echo ۲) کلید API برای !PROVIDER!
    if "!PROVIDER!"=="gemini" echo کلید رایگان: https://aistudio.google.com/api-keys
    if "!PROVIDER!"=="openai" echo کلید: https://platform.openai.com/api-keys
    if "!PROVIDER!"=="deepseek" echo کلید: https://platform.deepseek.com/api_keys
    if "!PROVIDER!"=="groq" echo کلید: https://console.groq.com/keys
    if "!PROVIDER!"=="xai" echo کلید: https://console.x.ai/
    if "!PROVIDER!"=="openrouter" echo کلید: https://openrouter.ai/keys
    if "!PROVIDER!"=="together" echo کلید: https://api.together.xyz/settings/api-keys
    echo کلیدها رو یکی‌یکی وارد کنید (خالی بذارید تا تموم بشه):
    echo.

    set i=1
    :key_loop
    set /p "k=کلید !i! (Enter = پایان): "
    if "!k!"=="" goto key_done
    if defined API_KEYS (
        set "API_KEYS=!API_KEYS!,!k!"
    ) else (
        set "API_KEYS=!k!"
    )
    set /a i+=1
    goto key_loop

    :key_done
    if not defined API_KEYS (
        echo خطا: حداقل یک کلید لازم است.
        pause
        exit /b 1
    )
    echo کلید ثبت شد.
) else (
    echo ۲) Ollama نیاز به کلید ندارد (لوکال).
)
echo.

echo ۳) مدل (Enter = پیش‌فرض provider):
if "!PROVIDER!"=="gemini" echo   مثال: gemini-flash-latest / gemini-3.8-flash
if "!PROVIDER!"=="openai" echo   مثال: gpt-4o-mini / gpt-4o
if "!PROVIDER!"=="deepseek" echo   مثال: deepseek-chat / deepseek-reasoner
if "!PROVIDER!"=="groq" echo   مثال: llama-3.3-70b-versatile
if "!PROVIDER!"=="xai" echo   مثال: grok-2-latest
if "!PROVIDER!"=="openrouter" echo   مثال: google/gemini-2.0-flash-001
if "!PROVIDER!"=="ollama" echo   مثال: llama3.2 / qwen2.5
if "!PROVIDER!"=="together" echo   مثال: meta-llama/Llama-3.3-70B-Instruct-Turbo
set /p "MODEL_NAME=مدل: "
echo.

echo زبان اصلی متن منبع رو انتخاب کنید:
echo  1) en (انگلیسی - اکثر اسکنلیشن‌ها)
echo  2) ja en (ژاپنی خام)
echo  3) ko en (کره‌ای خام)
echo  4) دستی وارد کنید
set /p "lang_choice=انتخاب [پیش‌فرض 1]: "
if "!lang_choice!"=="" set lang_choice=1

if "!lang_choice!"=="1" set OCR_LANG=en
if "!lang_choice!"=="2" set OCR_LANG=ja en
if "!lang_choice!"=="3" set OCR_LANG=ko en
if "!lang_choice!"=="4" (
    set /p "OCR_LANG=زبان OCR را وارد کنید: "
)
if not defined OCR_LANG set OCR_LANG=en
echo زبان OCR: !OCR_LANG!
echo.

echo ترتیب خواندن:
echo  1) rtl (راست به چپ - مانگا/مانهوای شرقی)
echo  2) ltr (چپ به راست - کمیک غربی)
set /p "order_choice=انتخاب [پیش‌فرض 1]: "
if "!order_choice!"=="" set order_choice=1

if "!order_choice!"=="2" (
    set READING_ORDER=ltr
) else (
    set READING_ORDER=rtl
)
echo ترتیب خواندن: !READING_ORDER!
echo.

echo ۵) ورودی رو بدید:
echo  - لینک صفحه (http/https)
echo  - مسیر فایل ZIP / PDF / پوشه تصاویر
echo  - یا فقط Enter بزنید تا مسیر فعلی رو چک کنیم
set /p "INPUT_PATH=ورودی: "
if "!INPUT_PATH!"=="" set INPUT_PATH=./pages

if not exist "!INPUT_PATH!" (
    echo !INPUT_PATH! | findstr /r "^https\?://" >nul
    if errorlevel 1 (
        echo هشدار: مسیر '!INPUT_PATH!' پیدا نشد. ادامه می‌دیم...
    )
)
echo ورودی: !INPUT_PATH!
echo.

echo فرمت خروجی:
echo  1) pdf
echo  2) html
echo  3) zip
set /p "out_choice=انتخاب [پیش‌فرض 1]: "
if "!out_choice!"=="" set out_choice=1
if "!out_choice!"=="1" set OUTPUT=.pdf
if "!out_choice!"=="2" set OUTPUT=.html
if "!out_choice!"=="3" set OUTPUT=.zip
if not defined OUTPUT set OUTPUT=.pdf
echo خروجی: !OUTPUT!
echo.

set FONT_DIR=fonts
if not exist "!FONT_DIR!" mkdir "!FONT_DIR!"
set BASE_URL=https://github.com/rastikerdar/vazirmatn/raw/master/fonts/ttf
for %%W in (Regular Medium SemiBold Bold ExtraBold Black Light) do (
    if not exist "!FONT_DIR!\Vazirmatn-%%W.ttf" (
        echo دانلود Vazirmatn-%%W.ttf ...
        curl -L -o "!FONT_DIR!\Vazirmatn-%%W.ttf" "!BASE_URL!/Vazirmatn-%%W.ttf"
    )
)
set FONT_PATH=!FONT_DIR!\Vazirmatn-Regular.ttf
set FONT_SHOUT=!FONT_DIR!\Vazirmatn-ExtraBold.ttf
set FONT_EXPLOSION=!FONT_DIR!\Vazirmatn-Black.ttf
set FONT_SFX=!FONT_DIR!\Vazirmatn-Black.ttf
set FONT_BLACK=!FONT_DIR!\Vazirmatn-Bold.ttf
set FONT_THOUGHT=!FONT_DIR!\Vazirmatn-Light.ttf
set FONT_WHISPER=!FONT_DIR!\Vazirmatn-Light.ttf
if not exist "!FONT_PATH!" (
    echo دانلود فونت شکست خورد. لطفاً دستی فونت را در fonts\ بگذارید.
    pause
    exit /b 1
)
echo فونت‌ها: Regular/ExtraBold/Black/Light آماده شد.
echo.

echo ========================================
echo شروع ترجمه با !PROVIDER! ...
echo ========================================
echo.

set "CMD=python manga_translator.py -i "!INPUT_PATH!" -o "!OUTPUT!" --font "!FONT_PATH!" --font-shout "!FONT_SHOUT!" --font-explosion "!FONT_EXPLOSION!" --font-sfx "!FONT_SFX!" --font-black "!FONT_BLACK!" --font-thought "!FONT_THOUGHT!" --font-whisper "!FONT_WHISPER!" --ocr-lang !OCR_LANG! --reading-order "!READING_ORDER!" --provider "!PROVIDER!""
if defined API_KEYS set "CMD=!CMD! --api-key "!API_KEYS!""
if defined MODEL_NAME set "CMD=!CMD! --model "!MODEL_NAME!""

!CMD!

echo.
echo ========================================
echo تمام شد! خروجی: !OUTPUT!
echo ========================================
pause
