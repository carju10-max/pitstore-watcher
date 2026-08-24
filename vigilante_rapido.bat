@echo off
rem Vigilante de pedidos cada minuto, sin ventana.
rem El de GitHub sigue corriendo aparte: este cubre mientras la laptop este
rem encendida, aquel cuando este apagada. No se duplican (comparten estado).
start "" "C:\Program Files\Python314\pythonw.exe" "C:\Users\HP\Documents\CARLOS\ClaudeCode\pitstore-watcher-cloud\vigilante_rapido.py"
