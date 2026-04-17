#!/bin/bash
echo "🛑 Deteniendo instancia anterior de WebTranslatorr..."
# Buscar y detener procesos previos corriendo en el puerto WTR_PORT o 9811
PORT=${WTR_PORT:-9811}
PID=$(lsof -t -i:$PORT)
if [ -n "$PID" ]; then
  kill -9 $PID
  echo "✅ Proceso $PID detenido en el puerto $PORT."
else
  echo "INFO: No se encontró ningún proceso en el puerto $PORT."
fi

# Ya que Python no se compila en el sentido estricto, 
# la fase de "compilación" aquí es instalar requisitos de ser necesario.
echo "📦 Verificando dependencias (pip install)..."
pip3 install -r requirements.txt --quiet || python3 -m pip install -r requirements.txt --quiet
echo "✅ Dependencias al día."

echo "🚀 Desplegando WebTranslatorr en segundo plano..."
nohup python3 main.py > webtranslatorr.log 2>&1 &

echo "✅ WebTranslatorr desplegado con éxito (PID: $!)."
echo "Puedes ver los logs corriendo: tail -f webtranslatorr.log"
