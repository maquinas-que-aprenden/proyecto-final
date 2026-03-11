#!/bin/bash
# Hook: Verifica si se debería actualizar el tracking de progreso
# Se ejecuta como prompt hook en el evento Stop
# Usa un LLM ligero para evaluar si la sesión produjo avances significativos

# Este hook es de tipo "prompt", no "command"
# Se define en settings.json con type: "prompt"
# Este archivo es solo documentación del prompt que se usa

# El prompt se define directamente en settings.json porque los hooks
# de tipo "prompt" no usan scripts externos
exit 0
