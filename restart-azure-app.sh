#!/bin/bash

echo "🔧 Reiniciando Mediotec en Azure App Service"
echo ""

read -p "Nombre del App Service (ej: mediotec-app): " APP_NAME
read -p "Grupo de Recursos (ej: rg-mediotecvial-prod): " RESOURCE_GROUP

echo ""
echo "Deteniendo app service..."
az webapp stop --name "$APP_NAME" --resource-group "$RESOURCE_GROUP"

sleep 5

echo "Limpiando archivos de caché..."
az webapp config appsettings set \
  --name "$APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --settings SCM_COMMAND_IDLE_TIMEOUT=1800

sleep 3

echo "Iniciando app service..."
az webapp start --name "$APP_NAME" --resource-group "$RESOURCE_GROUP"

echo ""
echo "Esperando a que inicie..."
sleep 10

echo "Verificando health check..."
APP_URL=$(az webapp show \
  --resource-group "$RESOURCE_GROUP" \
  --name "$APP_NAME" \
  --query defaultHostName -o tsv)

echo ""
echo "Probando: https://$APP_URL/health"
curl -s "https://$APP_URL/health" | head -c 200
echo ""
echo ""

if curl -s "https://$APP_URL/health" | grep -q "ok"; then
  echo "✓ Aplicacion esta corriendo"
else
  echo "Ver logs:"
  echo "  az webapp log tail --resource-group $RESOURCE_GROUP --name $APP_NAME"
fi
