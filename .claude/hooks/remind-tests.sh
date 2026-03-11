#!/bin/bash
# Hook: Recuerda escribir tests cuando se edita código fuente en src/
# Se ejecuta en PostToolUse para Edit/Write
# Si el archivo editado está en src/, recuerda al equipo que debería haber tests

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_input.file // empty')

# Solo actuar si el archivo está en src/
if [[ "$FILE_PATH" == *"/src/"* ]]; then
  # Extraer el nombre del módulo
  MODULE=$(echo "$FILE_PATH" | sed -n 's|.*/src/\([^/]*\)/.*|\1|p')

  # Verificar si existe test para este módulo
  TEST_DIR="$(echo "$INPUT" | jq -r '.cwd')/tests"
  if [ -d "$TEST_DIR" ]; then
    TEST_FILES=$(find "$TEST_DIR" -name "test_${MODULE}*.py" 2>/dev/null | head -1)
    if [ -z "$TEST_FILES" ]; then
      echo "Recordatorio: Has modificado src/${MODULE}/ pero no existe test_${MODULE}.py en tests/. Considera escribir tests para este módulo."
    fi
  fi
fi

exit 0
