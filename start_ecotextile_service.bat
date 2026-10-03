@echo off
cd /d "D:\Final file of the software\fulll end final\EcoTextile_Enterprises_Polished_ScannerFix_Clean_TelemetryDelete_ReportImport\EcoTextile_Polished\Production"
"D:\Final file of the software\fulll end final\EcoTextile_Enterprises_Polished_ScannerFix_Clean_TelemetryDelete_ReportImport\EcoTextile_Polished\venv\Scripts\python.exe" -m waitress --listen=0.0.0.0:5000 app:app
