@echo off
cd /d "%~dp0"
echo ポートフォリオ・タイムマシンを起動しています...
echo ブラウザが自動で開きます。開かない場合は表示されるURLをブラウザに貼ってください。
echo このウィンドウは閉じないでください(閉じるとアプリが止まります)。
python -m streamlit run app.py
pause
