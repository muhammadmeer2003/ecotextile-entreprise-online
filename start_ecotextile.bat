@echo off
cd /d "D:\Final file of the software\EcoTextile_Enterprises_ClientDemo_Mobile_v2\EcoTextile_Enterprises_FINAL_Production - Copy"
"D:\Final file of the software\EcoTextile_Enterprises_ClientDemo_Mobile_v2\venv\Scripts\python.exe" -m waitress --listen=0.0.0.0:5000 app:app         