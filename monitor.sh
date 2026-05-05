#!/bin/bash
# Monitor — Verificar se agente está progredindo ou travado

echo "🔍 MONITORAMENTO — Gold Modelagem Execution"
echo "============================================"
echo ""

while true; do
    echo "[$(date '+%H:%M:%S')] Checando status..."

    # 1. Ver se há processo Python ativo
    PY_PROCS=$(pgrep -f "python.*cli.main.*run" | wc -l)
    if [ $PY_PROCS -gt 0 ]; then
        echo "  ✅ Processo Python ativo: $PY_PROCS"
    else
        echo "  ❌ Nenhum processo Python rodando"
    fi

    # 2. Ver se log está sendo atualizado
    if [ -f "output/gold_creation.log" ]; then
        LAST_MOD=$(($(date +%s) - $(stat -f%m output/gold_creation.log)))
        echo "  ⏱️  Log atualizado há ${LAST_MOD}s atrás"

        if [ $LAST_MOD -gt 120 ]; then
            echo "  ⚠️  ALERTA: Log congelado há mais de 2 minutos!"
        fi

        # 3. Últimas 5 linhas do log
        echo ""
        echo "  📋 Últimas mensagens:"
        tail -5 output/gold_creation.log | sed 's/^/     /'
    fi

    # 4. Ver se há notebooks sendo criados
    if [ -f "output/gold_notebooks_manual.md" ]; then
        NOTEBOOKS=$(grep -c "gld_" output/gold_notebooks_manual.md 2>/dev/null || echo 0)
        echo ""
        echo "  🎯 Notebooks criados: $NOTEBOOKS/8"
    fi

    echo ""
    echo "Aguardando 30s para próxima verificação... (pressione Ctrl+C para parar)"
    sleep 30
done
